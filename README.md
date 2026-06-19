
# Marker-Signal-Void
# Marker Signal Void (MSV): Bangla Rumour Detection

Official implementation of the paper:

**Marker Signal Void: Linguistic Deception Fingerprinting and Transformer Benchmarking on a Domain-Stratified Bangla Rumour Corpus**

## Overview

Rumour detection in Bangla remains largely under-explored despite the growing societal impact of online misinformation. This repository introduces **MisInfo-11K**, the first domain-stratified Bangla rumour detection dataset, along with **14 linguistically motivated deception markers** and a novel analytical framework called **Marker Signal Void (MSV)**.

MSV estimates the theoretical upper bound of surface-level rumour detection by identifying instances that carry no net discriminative linguistic signal relative to authentic content.

---

## Contributions

* 📊 **MisInfo-11K**: A domain-stratified Bangla rumour corpus containing **11,198 headlines**.
* 🔍 **14 Linguistic Markers** for Bangla misinformation analysis.
* 🧠 **Marker Signal Void (MSV)** framework for measuring the limits of surface-level detection.
* 🤖 Comprehensive benchmarking of:

  * Logistic Regression
  * SVM
  * Random Forest
  * XGBoost
  * BanglaBERT
  * MuRIL
  * XLM-RoBERTa
* 📈 Domain-level deception fingerprint analysis across seven misinformation domains.

---

## Dataset Statistics

| Split      | Total  | Rumour | Non-Rumour |
| ---------- | ------ | ------ | ---------- |
| Train      | 8,198  | 3,998  | 4,200      |
| Validation | 1,400  | 700    | 700        |
| Test       | 1,400  | 700    | 700        |
| Total      | 11,198 | 5,398  | 5,800      |

### Domains

* Political
* Health
* Religious
* Cultural
* Sports
* Celebrity
* International

---

## Main Results

| Model                            | Macro-F1   |
| -------------------------------- | ---------- |
| Logistic Regression + TF-IDF     | 0.9693     |
| SVM + TF-IDF                     | 0.9643     |
| XGBoost + TF-IDF                 | 0.9693     |
| Random Forest + TF-IDF + Markers | 0.9750     |
| XLM-RoBERTa                      | 0.9736     |
| BanglaBERT                       | 0.9771     |
| MuRIL                            | **0.9800** |

### Marker Signal Void (MSV)

* Surface-level theoretical ceiling: **Macro-F1 = 0.9843**
* Best model (MuRIL): **Macro-F1 = 0.9800**
* Only **22 test rumours (3.1%)** fall inside the Marker Signal Void.

---

## Repository Structure

```text
.
├── data/
├── markers/
├── traditional_models/
├── transformers/
├── analysis/
├── figures/
├── requirements.txt
└── README.md
```

---

## Installation

```bash
git clone https://github.com/<your-username>/<repo-name>.git

cd <repo-name>

pip install -r requirements.txt
```

---

## Training

### MuRIL

```bash
python transformers/muril.py
```

### BanglaBERT

```bash
python transformers/banglabert.py
```

### XLM-RoBERTa

```bash
python transformers/xlmr.py
```

### Traditional Models

```bash
python traditional_models/random_forest.py
```

---

## Reproducibility

All experiments were conducted using:

* Fixed random seed: 42
* Maximum sequence length: 128
* Batch size: 16
* Learning rate: 2e-5
* AdamW optimizer

For complete implementation details, statistical analyses, and experimental settings, please refer to the accompanying paper.

---

## Citation

If you use this work, please cite:

```bibtex
@article{msv2026,
  title={Marker Signal Void: Linguistic Deception Fingerprinting and Transformer Benchmarking on a Domain-Stratified Bangla Rumour Corpus},
  author={Anonymous},
  year={2026}
}
```

---

## License

This project is released under the MIT License.

---

## Contact

For questions, collaborations, or dataset access requests, please open an issue or contact the authors.
