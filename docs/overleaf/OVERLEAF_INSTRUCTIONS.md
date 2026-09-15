# Overleaf Setup & Presentation QR Code Instructions

This guide explains how to compile the **TRACE-X Research & Technical Whitepaper** on Overleaf, download the court-grade PDF, and generate a QR Code for your **Smart India Hackathon (SIH 2026)** PowerPoint presentation.

---

## 📄 Files Created in `docs/overleaf/`

1. **[`standalone_main.tex`](file:///home/akshay/trace-x/docs/overleaf/standalone_main.tex)**:  
   * **1-Click Standalone File** with embedded bibliography and citations.
   * Compiles immediately in any Overleaf project without needing extra file uploads.
2. **[`main.tex`](file:///home/akshay/trace-x/docs/overleaf/main.tex)**:  
   * Standard multi-file LaTeX source referencing `references.bib`.
3. **[`references.bib`](file:///home/akshay/trace-x/docs/overleaf/references.bib)**:  
   * Complete BibTeX database with 22 authentic peer-reviewed papers (IEEE, ACM, Springer), Indian statutory acts, and FATF circulars.

---

## 🚀 How to Compile on Overleaf (Under 60 Seconds)

### Method 1: The 1-Click Method (Easiest)
1. Open [Overleaf.com](https://www.overleaf.com) and log in.
2. Click **New Project** $\to$ **Blank Project** $\to$ Name it `TRACE-X-Research-Whitepaper`.
3. Select all text in `main.tex` on Overleaf and **delete it**.
4. Open [`docs/overleaf/standalone_main.tex`](file:///home/akshay/trace-x/docs/overleaf/standalone_main.tex) on your computer, **copy everything**, and **paste it** into Overleaf's `main.tex`.
5. Click the green **Recompile** button.
6. Click the **Download PDF** button next to Recompile.

### Method 2: Multi-File Method (With `.bib` File)
1. Create a Blank Project on Overleaf.
2. Copy the content of [`docs/overleaf/main.tex`](file:///home/akshay/trace-x/docs/overleaf/main.tex) into `main.tex`.
3. Click the **New File** icon (top-left of Overleaf), name it `references.bib`, and paste the content of [`docs/overleaf/references.bib`](file:///home/akshay/trace-x/docs/overleaf/references.bib).
4. Click **Recompile**.

---

## 📱 How to Generate the Slide QR Code for SIH

Once your PDF is downloaded:

### Step 1: Upload the PDF Online
* **Option A (Google Drive)**:
  1. Upload the downloaded `TRACE-X-Research-Whitepaper.pdf` to your Google Drive.
  2. Right-click the file $\to$ **Share** $\to$ Change General Access to **"Anyone with the link can view"**.
  3. Copy the link.
* **Option B (GitHub)**:
  1. Commit the PDF to your GitHub repo (e.g., in `docs/TRACE-X_Research_Whitepaper.pdf`) or upload it to a GitHub Release.
  2. Copy the raw/view link.

### Step 2: Generate the QR Code
1. Go to any free QR code generator (e.g. [qr-code-generator.com](https://www.qr-code-generator.com/) or [me-qr.com](https://me-qr.com/)).
2. Paste the public link to your PDF.
3. Download the QR code image (`.png`).

### Step 3: Add to your SIH PowerPoint Slide
Place the QR code on your **Research & Reference** slide with the following suggested layout:

```text
+-----------------------------------------------------------------------+
|  RESEARCH FOUNDATIONS, BENCHMARKS & LEGAL DEFENSIBILITY                |
+-----------------------------------------------------------------------+
|                                                                       |
|  [ QR CODE IMAGE ]         📄 SCAN TO VIEW COMPLETE RESEARCH DOSSIER  |
|                            • Problem Statement: SIH26183 Compliance    |
|                            • 12-Factor ML Risk Scoring Formulation    |
|                            • Dijkstra VASP Attribution Decay Proof    |
|                            • Sec 65B Indian Evidence Act Admissibility|
|                            • Comparative Benchmark: Chainalysis vs Ours|
|                            • 22+ Peer-Reviewed IEEE/ACM Citations      |
|                                                                       |
|  Direct Link: https://drive.google.com/file/d/.../view                 |
+-----------------------------------------------------------------------+
```

---

## 📑 Summary of What Judges See When Scanning

When evaluators scan your QR code during the presentation, they see an **IEEE/ACM formatted 5-page technical report** featuring:
1. **The SIH26183 Problem Statement & Criminal Modus Operandi**: Breakdown of Peel Chains, CoinJoins, Cross-chain bridges, and Hawala-style nested exchange accounts.
2. **Comprehensive Literature Review**: Mathematical citations of Ron & Shamir (2013), Meiklejohn et al. (2013), and Weber et al. (Elliptic GCN benchmark).
3. **Comparative Analysis Matrix**: Side-by-side feature comparison of TRACE-X against **Chainalysis Reactor, Elliptic Navigator, TRM Labs, and QLUE**.
4. **Algorithmic Formulations & Proofs**:
   * Pruned BFS Graph Traversal algorithm.
   * Dijkstra Shortest-Path Attribution with confidence decay equation:
     $$C(P) = C_0(e) \cdot \exp(-\lambda \cdot k) \cdot \prod_{i=1}^k \eta(e_i)$$
   * 12-Factor Explainable ML Risk Matrix with explicit weights ($w_j$) and base scores.
5. **Indian Statutory Defensibility**: Complete compliance analysis under **Section 65B of the Indian Evidence Act, 1872** / **Section 63 of Bharatiya Sakshya Adhiniyam (BSA), 2023**, PMLA 2002, and FATF Recommendation 16 (Travel Rule).
6. **Empirical Benchmarks**: Traversal times (1 to 5 hops in milliseconds) across the 5 national cybercrime scenarios (DeFi Flash Loan, LockBit Ransomware, Hydra Darknet, Russian Sanctions Evasion).
7. **22 Peer-Reviewed References**: Full academic and statutory bibliography.
