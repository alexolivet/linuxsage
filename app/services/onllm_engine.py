"""On-device/offline chat engine using the OnLLM approach.

This module intentionally mirrors the core logic from the OnLLM project
(https://github.com/daslearning-org/OnLLM):
- ONNX Runtime decoder-only generation with KV cache
- HuggingFace `tokenizers` Tokenizer
- Simple sampling (temperature + top_p)

It is written as a *library* (no UI code) so it can be used from any Kivy
screen (e.g. Tab3).

Model layout expected (same as OnLLM release tarballs):
    <model_dir>/<model_name>/
        config.json
        tokenizer.json
        onnx/model_int8.onnx

Note: the first run still requires internet to download the model files.
"""

from __future__ import annotations

import json
import os
import tarfile
import threading
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from kivy.logger import Logger
from kivy.utils import platform

try:
    import numpy as np
except Exception as e:  # pragma: no cover
    np = None  # type: ignore
    Logger.exception(f"OnLLM: failed to import numpy: {e}")

try:
    import requests
except Exception as e:  # pragma: no cover
    requests = None  # type: ignore
    Logger.exception(f"OnLLM: failed to import requests: {e}")

ONNXRUNTIME_IMPORT_ERROR: Exception | None = None
TOKENIZERS_IMPORT_ERROR: Exception | None = None

try:
    from onnxruntime import InferenceSession
except Exception as e:  # pragma: no cover
    InferenceSession = None  # type: ignore
    ONNXRUNTIME_IMPORT_ERROR = e
    Logger.exception(f"OnLLM: failed to import onnxruntime: {e}")

try:
    from tokenizers import Tokenizer
except Exception as e:  # pragma: no cover
    Tokenizer = None  # type: ignore
    TOKENIZERS_IMPORT_ERROR = e
    Logger.exception(f"OnLLM: failed to import tokenizers: {e}")

NON_LINUX_REFUSAL = "I am a Linux specialist and can only assist with Linux questions."

# A strict, structured prompt (with few-shot examples) works better for small models.
LINUX_SYSTEM_PROMPT = """ROLE
You are Linux Sage, a Linux helpdesk/trainer.

SCOPE (answer ONLY these topics)
- Linux shell commands and CLI usage
- Linux system administration (users, permissions, services, logs)
- Package management (apt, dnf, yum, pacman)
- Networking on Linux (ip/ss/ssh/curl/wget)
- Shell scripting (bash)
- Troubleshooting on Linux

HARD RULES
- If the question is NOT Linux-related, reply with EXACTLY this single sentence and nothing else:
  I am a Linux specialist and can only assist with Linux questions.
- Do not answer general trivia, non-Linux OS questions, or unrelated programming topics.
- Prefer concise, command-first answers.
- If you are unsure, ask one clarifying question OR suggest a safe diagnostic command.

ANSWER FORMAT
1) Short explanation (1–2 lines)
2) Commands in a code block
3) Optional: brief notes / common pitfalls

FEW-SHOT EXAMPLES
User: What is the capital of France?
Assistant: I am a Linux specialist and can only assist with Linux questions.

User: Write a poem.
Assistant: I am a Linux specialist and can only assist with Linux questions.

User: How do I check disk usage on Linux?
Assistant: Disk usage can be checked per filesystem or per directory.
```sh
df -h
# directory usage
du -sh /path
```

User: How do I list hidden files?
Assistant: Hidden files start with a dot.
```sh
ls -la
```
"""

# Lightweight keyword gate to reduce off-topic responses (small models can drift).
_LINUX_KEYWORDS = {
    "linux",
    "ubuntu",
    "debian",
    "fedora",
    "arch",
    "centos",
    "alpine",
    "bash",
    "shell",
    "terminal",
    "sudo",
    "chmod",
    "chown",
    "systemctl",
    "systemd",
    "journalctl",
    "apt",
    "apt-get",
    "dpkg",
    "dnf",
    "yum",
    "pacman",
    "apk",
    "grep",
    "awk",
    "sed",
    "find",
    "ssh",
    "scp",
    "rsync",
    "cron",
    "crontab",
    "tar",
    "gzip",
    "zip",
    "unzip",
    "mount",
    "umount",
    "fstab",
    "kernel",
    "dmesg",
    "log",
    "curl",
    "wget",
    "ping",
    "ip ",
    "ss ",
}

def _format_import_error(name: str, exc: Exception | None) -> str:
    if exc is None:
        return f"{name}: unavailable for an unknown reason"
    return f"{name}: {type(exc).__name__}: {exc}"


def get_runtime_dependency_status() -> dict[str, str]:
    return {
        "numpy": "ok" if np is not None else "missing",
        "requests": "ok" if requests is not None else "missing",
        "onnxruntime": "ok"
        if InferenceSession is not None
        else _format_import_error("onnxruntime", ONNXRUNTIME_IMPORT_ERROR),
        "tokenizers": "ok"
        if Tokenizer is not None
        else _format_import_error("tokenizers", TOKENIZERS_IMPORT_ERROR),
    }




@dataclass(frozen=True)
class OnllmModelSpec:
    name: str
    url: str
    size_label: str
    tokens: List[str]  # [init, start, end]
    eos_ids: List[str]
    att_mask: bool = True


DEFAULT_MODELS: Dict[str, OnllmModelSpec] = {
    # This matches the default model in the upstream OnLLM app.
    "smollm2-135m": OnllmModelSpec(
        name="smollm2-135m",
        url="https://github.com/daslearning-org/OnLLM/releases/download/vOnnxModels/smollm2-135m.tar.gz",
        size_label="~95MB",
        tokens=["", "<|im_start|>", "<|im_end|>"],
        eos_ids=["<|endoftext|>"],
        att_mask=True,
    ),
}


class OnllmDownloadError(RuntimeError):
    pass


class OnnxChatEngine:
    """Load an OnLLM-style ONNX model and generate tokens for a chat prompt."""

    @staticmethod
    def _last_user_text(messages: List[Dict[str, str]]) -> str:
        for msg in reversed(messages or []):
            if msg.get("role") == "user":
                return str(msg.get("content") or "")
        return ""

    @staticmethod
    def _looks_linux_related(text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return True
        # If Tab3 injected DB context, treat as Linux-related.
        if "context (local knowledge base)" in t:
            return True
        return any(k in t for k in _LINUX_KEYWORDS)

    def __init__(
        self,
        model_dir: str,
        models: Optional[Dict[str, OnllmModelSpec]] = None,
    ) -> None:
        self.model_dir = model_dir
        self.models = models or DEFAULT_MODELS

        self._lock = threading.RLock()
        self._stop_event = threading.Event()

        # Loaded model state
        self.model_name: Optional[str] = None
        self.decoder_session: Optional[InferenceSession] = None
        self.tokenizer: Optional[Tokenizer] = None
        self.num_key_value_heads: int = 0
        self.head_dim: int = 0
        self.num_hidden_layers: int = 0
        self.eos_token_ids: List[int] = []
        self.use_att_mask: bool = True

    # ----------------------------
    # Model files / download
    # ----------------------------

    def model_path(self, model_name: str) -> str:
        return os.path.join(self.model_dir, model_name)

    def check_model_files(self, model_name: str) -> bool:
        base = self.model_path(model_name)
        required = [
            os.path.join(base, "config.json"),
            os.path.join(base, "tokenizer.json"),
            os.path.join(base, "onnx", "model_int8.onnx"),
        ]
        return all(os.path.exists(p) for p in required)

    def download_and_extract(
        self,
        model_name: str,
        progress_cb: Optional[Callable[[int, int], None]] = None,
        timeout_s: int = 60,
    ) -> None:
        """Download the model, extract it, and load it immediately.

        Raises:
            OnllmDownloadError: For any download/extract/load failure.
        """

        if requests is None:
            raise OnllmDownloadError("requests is not installed")

        spec = self.models.get(model_name)
        if not spec:
            raise OnllmDownloadError(f"Unknown model: {model_name}")

        # 1) Download
        os.makedirs(self.model_dir, exist_ok=True)
        tar_path = os.path.join(self.model_dir, f"{model_name}.tar.gz")

        Logger.info(f"OnLLM: downloading {model_name} -> {tar_path}")
        try:
            with requests.get(spec.url, stream=True, timeout=timeout_s) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0) or 0)
                downloaded = 0
                with open(tar_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(downloaded, total)
        except Exception as e:
            raise OnllmDownloadError(f"Download failed: {e}") from e

        # 2) Extract
        Logger.info(f"OnLLM: extracting {tar_path} -> {self.model_dir}")
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=self.model_dir)
        except Exception as e:
            raise OnllmDownloadError(f"Extract failed: {e}") from e
        finally:
            # Best-effort cleanup.
            try:
                os.remove(tar_path)
            except OSError:
                pass

        # 3) Verify
        if not self.check_model_files(model_name):
            raise OnllmDownloadError(
                f"Model extracted but required files are missing for: {model_name}"
            )

        # 4) Load
        Logger.info(f"OnLLM: download complete, loading model '{model_name}'...")
        try:
            self.load(model_name)
        except Exception as e:
            raise OnllmDownloadError(
                f"Model files present but load() failed for {model_name}: {e}"
            ) from e

        Logger.info(f"OnLLM: model '{model_name}' loaded successfully and ready for chat!")

    # ----------------------------
    # Loading / generation
    # ----------------------------

    def stop(self) -> None:
        self._stop_event.set()

    def reset_stop(self) -> None:
        self._stop_event.clear()

    def load(self, model_name: str) -> None:
        """Load tokenizer + ONNX session for `model_name`."""
        if np is None:
            raise RuntimeError(
                "numpy is not installed. Install numpy to use offline chat."
            )

        if InferenceSession is None or Tokenizer is None:
            details = []
            if InferenceSession is None:
                details.append(_format_import_error("onnxruntime", ONNXRUNTIME_IMPORT_ERROR))
            if Tokenizer is None:
                details.append(_format_import_error("tokenizers", TOKENIZERS_IMPORT_ERROR))
            raise RuntimeError("; ".join(details))

        spec = self.models.get(model_name)
        if not spec:
            raise ValueError(f"Unknown model: {model_name}")

        if not self.check_model_files(model_name):
            raise FileNotFoundError(
                f"Model files not found for '{model_name}'. Download first."
            )

        base = self.model_path(model_name)
        with open(os.path.join(base, "config.json"), "r", encoding="utf-8") as f:
            config = json.load(f)

        tokenizer = Tokenizer.from_file(os.path.join(base, "tokenizer.json"))

        self.num_key_value_heads = int(config["num_key_value_heads"])
        self.head_dim = int(config["head_dim"])
        self.num_hidden_layers = int(config["num_hidden_layers"])
        self.use_att_mask = bool(spec.att_mask)

        primary_eos = spec.tokens[2]
        eos_token_ids = [tokenizer.token_to_id(primary_eos)]
        for eos in spec.eos_ids:
            eos_token_ids.append(tokenizer.token_to_id(str(eos)))
        eos_token_ids = [x for x in eos_token_ids if x is not None]

        # Provider selection: mirrors OnLLM's preferences, but avoid
        # requesting CUDA when it's not available (prevents noisy warnings).
        android_providers = [
            "XnnpackExecutionProvider",
            "CPUExecutionProvider",
        ]

        desktop_providers = ["CPUExecutionProvider"]
        try:
            import onnxruntime as ort  # type: ignore

            available = set(ort.get_available_providers() or [])
            if "CUDAExecutionProvider" in available:
                desktop_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            # If introspection fails, stick to CPU only.
            desktop_providers = ["CPUExecutionProvider"]

        providers = android_providers if platform == "android" else desktop_providers

        onnx_path = os.path.join(base, "onnx", "model_int8.onnx")
        try:
            sess = InferenceSession(onnx_path, providers=providers)
        except Exception:
            # Fallback: let ORT pick defaults.
            sess = InferenceSession(onnx_path)

        Logger.info(f"OnLLM: ORT providers: {getattr(sess, 'get_providers', lambda: [])()}")

        with self._lock:
            self.model_name = model_name
            self.tokenizer = tokenizer
            self.decoder_session = sess
            self.eos_token_ids = [int(x) for x in eos_token_ids]

    def apply_chat_template(
        self, messages: List[Dict[str, str]], add_generation_prompt: bool
    ) -> np.ndarray:
        """Create input_ids for the model.

        This follows the OnLLM `apply_chat_template` logic.

        Note: We always inject a Linux-specialist system prompt as the *first*
        system message to keep the assistant on-topic.
        """
        if not self.model_name:
            raise RuntimeError("Model not loaded")
        spec = self.models[self.model_name]
        assert self.tokenizer is not None

        init_prompt, start_prompt, end_prompt = spec.tokens

        # Avoid mutating caller-provided messages.
        all_messages: List[Dict[str, str]] = [
            {"role": "system", "content": LINUX_SYSTEM_PROMPT},
            *messages,
        ]

        prompt = init_prompt
        for msg in all_messages:
            role = msg["role"]
            content = msg["content"].strip()
            if role == "system":
                prompt += f"{start_prompt}system\n{content}{end_prompt}\n"
            elif role == "user":
                prompt += f"{start_prompt}user\n{content}{end_prompt}\n"
            else:  # assistant/model
                prompt += f"{start_prompt}assistant\n{content}{end_prompt}\n"

        if add_generation_prompt:
            prompt += f"{start_prompt}assistant\n"

        if np is None:
            raise RuntimeError("numpy is not installed")

        encoding = self.tokenizer.encode(prompt, add_special_tokens=False)
        input_ids = np.array([encoding.ids], dtype=np.int64)
        return input_ids

    @staticmethod
    def _sample_logits(logits: np.ndarray, temperature: float = 0.7, top_p: float = 0.9) -> np.ndarray:
        """Sampling function (temperature + nucleus sampling), copied from OnLLM."""
        if np is None:
            raise RuntimeError("numpy is not installed")

        logits = logits.astype(np.float64)
        logits = logits / max(temperature, 1e-5)
        exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

        sorted_indices = np.argsort(probs[0])[::-1]
        sorted_probs = probs[0, sorted_indices]
        cumulative_probs = np.cumsum(sorted_probs)

        cutoff = np.where(cumulative_probs > top_p)[0]
        cutoff = cutoff[0] + 1 if len(cutoff) > 0 else len(probs[0])

        probs[:, sorted_indices[cutoff:]] = 0
        probs /= np.sum(probs, axis=-1, keepdims=True) + 1e-10

        next_token = np.random.choice(len(probs[0]), p=probs[0])
        return np.array([[next_token]], dtype=np.int64)

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Iterable[str]:
        """Yield decoded token text increments.

        Note: We enforce a lightweight "Linux-only" gate. If the last user
        message doesn't look Linux-related, we immediately return a refusal.
        """

        last_user = self._last_user_text(messages)
        if last_user and not self._looks_linux_related(last_user):
            yield NON_LINUX_REFUSAL
            return

        with self._lock:
            if not self.decoder_session or not self.tokenizer or not self.model_name:
                raise RuntimeError("Model not loaded")
            sess = self.decoder_session
            tokenizer = self.tokenizer

            num_key_value_heads = self.num_key_value_heads
            head_dim = self.head_dim
            num_hidden_layers = self.num_hidden_layers
            eos_token_ids = list(self.eos_token_ids)
            use_att_mask = self.use_att_mask

        self.reset_stop()

        input_ids = self.apply_chat_template(messages, add_generation_prompt=True)
        batch_size = input_ids.shape[0]

        if np is None:
            raise RuntimeError("numpy is not installed")

        # KV cache init (same shape logic as OnLLM)
        past_key_values: Dict[str, np.ndarray] = {
            f"past_key_values.{layer}.{kv}": np.zeros(
                [batch_size, num_key_value_heads, 1, head_dim],
                dtype=np.float32,
            )[:, :, :0, :]
            for layer in range(num_hidden_layers)
            for kv in ("key", "value")
        }

        if use_att_mask:
            attention_mask = np.ones_like(input_ids, dtype=np.int64)
        else:
            attention_mask = None

        position_ids = np.tile(np.arange(0, input_ids.shape[-1]), (batch_size, 1))

        for _ in range(int(max_new_tokens)):
            if self._stop_event.is_set():
                break

            feeds = {
                "input_ids": input_ids,
                "position_ids": position_ids,
                **past_key_values,
            }
            if use_att_mask and attention_mask is not None:
                feeds["attention_mask"] = attention_mask

            logits, *present_key_values = sess.run(None, feeds)

            input_ids = self._sample_logits(logits[:, -1, :], temperature=temperature, top_p=top_p)

            if use_att_mask and attention_mask is not None:
                attention_mask = np.concatenate(
                    [attention_mask, np.ones_like(input_ids, dtype=np.int64)], axis=-1
                )

            position_ids = position_ids[:, -1:] + 1
            for j, key in enumerate(past_key_values):
                past_key_values[key] = present_key_values[j]

            if np.isin(input_ids, eos_token_ids).any():
                break

            piece = tokenizer.decode(input_ids[0], skip_special_tokens=True)
            if piece:
                yield piece

    def generate_full(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        return "".join(
            self.generate_stream(
                messages,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
            )
        )
