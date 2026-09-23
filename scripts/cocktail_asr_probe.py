"""Xiaomi-CocktailASR-1 目标说话人识别探针。

在 GPU 服务器上独立运行（不依赖 voice_focus_asr 包）：

    python cocktail_asr_probe.py --model-dir ./model --cases cases.tsv --audio-root ./audio \
        --output report.json

cases.tsv 列：case_id, kind, mixture, ref, expected_text
kind：positive（目标在场，有参考文本）、absent（目标缺席，期望空输出）、
swap（同会议另一说话人的声纹，诊断用）、clean（单人语音）、random_ref（完整声纹、模型内部随机截取）。

除 random_ref 外，声纹都预先截成能量最高的固定 4 秒窗口：模型会把超过 4 秒的参考音频
随机截成 1–4 秒，固定窗口才能复现结果。
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from transformers import AutoModel

SAMPLE_RATE = 16_000
REF_SECONDS = 4.0


def load_wav(path: Path) -> np.ndarray:
    data, rate = sf.read(str(path), dtype="float32")
    if rate != SAMPLE_RATE or data.ndim != 1:
        raise ValueError(f"{path}: 需要 16 kHz 单声道，实际 {rate} Hz, shape={data.shape}")
    return data


def loudest_window(audio: np.ndarray, seconds: float = REF_SECONDS) -> np.ndarray:
    size = int(seconds * SAMPLE_RATE)
    if len(audio) <= size:
        return audio
    step = SAMPLE_RATE // 4
    starts = range(0, len(audio) - size + 1, step)
    best = max(starts, key=lambda s: float(np.sum(audio[s : s + size] ** 2)))
    return audio[best : best + size]


def normalize(text: str) -> str:
    return re.sub(r"[^\w]", "", text).lower().replace("_", "")


def cer(reference: str, hypothesis: str) -> float | None:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return None
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1] / len(ref)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cot", action="store_true", help="同时对 positive 用例跑思维链模式")
    args = parser.parse_args()

    with args.cases.open(encoding="utf-8") as f:
        cases = list(csv.DictReader(f, delimiter="\t"))

    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model = (
        AutoModel.from_pretrained(
            str(args.model_dir), trust_remote_code=True, torch_dtype=torch.bfloat16
        )
        .cuda()
        .eval()
    )
    load_seconds = time.perf_counter() - started
    weights_gib = torch.cuda.memory_allocated() / 2**30

    def run(mixture: np.ndarray, ref: np.ndarray, cot: bool = False) -> tuple[str, float]:
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        text = model(mixture, ref, cot=cot)
        torch.cuda.synchronize()
        return text, time.perf_counter() - t0

    first = cases[0]
    run(
        load_wav(args.audio_root / first["mixture"]),
        loudest_window(load_wav(args.audio_root / first["ref"])),
    )

    results = []
    for case in cases:
        mixture = load_wav(args.audio_root / case["mixture"])
        full_ref = load_wav(args.audio_root / case["ref"])
        repeats = 3 if case["kind"] == "random_ref" else 1
        for repeat in range(repeats):
            if case["kind"] == "random_ref":
                random.seed(1000 + repeat)
                ref = full_ref
            else:
                ref = loudest_window(full_ref)
            text, seconds = run(mixture, ref)
            row = {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "repeat": repeat,
                "mixture_seconds": round(len(mixture) / SAMPLE_RATE, 2),
                "infer_seconds": round(seconds, 3),
                "rtf": round(seconds / (len(mixture) / SAMPLE_RATE), 3),
                "expected_text": case["expected_text"],
                "text": text,
                "empty": normalize(text) == "",
                "cer": cer(case["expected_text"], text),
            }
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if args.cot and case["kind"] == "positive":
                text, seconds = run(mixture, ref, cot=True)
                answer = re.search(r"<answer>(.*?)</answer>", text, re.S)
                cot_row = dict(row, kind="positive_cot", infer_seconds=round(seconds, 3))
                cot_row.update(
                    text=text, cer=cer(case["expected_text"], answer.group(1) if answer else text)
                )
                results.append(cot_row)
                print(json.dumps(cot_row, ensure_ascii=False), flush=True)

    report = {
        "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "load_seconds": round(load_seconds, 1),
        "weights_vram_gib": round(weights_gib, 2),
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
