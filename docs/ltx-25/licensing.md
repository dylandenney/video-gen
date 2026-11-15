# Licensing

> **Not legal advice.** This is a technical summary for routing to a legal contact. Items marked **LEGAL** need review before commercial launch. (Also flagged for compliance/data-governance routing per company policy.)

**Bottom line:** LTX-2.5 weights are under the **LTX-2.x Community License** (not open source; code is Apache-2.0). Free for any purpose for entities under **$10M annual revenue**; at/above that, any non-test commercial use — including end-user-facing use and training LoRAs for commercial use — needs a **paid Commercial Use Agreement** (licensing@ltx.io). LoRAs/fine-tunes are Derivatives bound by the same terms. Outputs are yours, subject to the Acceptable Use Policy and AI-transparency obligations.

Source: https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x (accessed 2026-11-15); README model table https://github.com/Lightricks/LTX-2 **[V]**.

## Key terms **[V]**
- **Two licenses:** repo code = Apache 2.0; models = LTX-2.x Community License; Apache grants no rights in the model (s2.3).
- **Revenue threshold (s2.1):** entities with annual revenue >= $10,000,000 must obtain a paid license for any use other than Non-Commercial Purpose. Breach -> back fees at standard commercial rates within 30 days of demand.
- **Non-Commercial Purpose (s2.2):** personal hobby/research not connected to any business/employer; or company testing/evaluation in a non-production environment. Explicitly **not** non-commercial: revenue-generating use (direct/indirect), anything that impacts end users, training/fine-tuning/distilling for commercial use.
- **Derivatives (s1.5):** fine-tuned weights, LoRAs, adapted checkpoints, architectures based on LTX-2.x, and models trained on LTX outputs/synthetic data to mimic it.
- **Distribution (s3):** pass on the license + Attachment A use restrictions; Derivatives distributed under same terms; s3.5 restricts transferring Derivatives (incl. LoRA adapters) — recipients must be bound/licensed.
- **Output (s5):** Licensor claims no rights in Outputs; you are accountable for inputs/outputs.
- **AI regulations (s6):** comply with EU AI Act, California AI Transparency Act; must **not remove/disable watermarking, provenance metadata, latent disclosures**; Licensor may remotely restrict or update; expected to use latest version.
- **Acceptable Use Policy** (Attachment A, incorporated by URL, updatable): https://static.lightricks.com/legal/ltx-acceptable-use-policy.pdf (not read).
- **Governing law:** New York, USA (s12).
- LTX output marking for EU AI Act: https://docs.ltx.io/api-documentation/transparency/eu-ai-act.md (API docs; local-model applicability not confirmed [A]).

## Items for legal contact (LEGAL)
1. **Revenue threshold:** Mountville (and any parent/affiliate) revenue vs. $10M — "Entity" definition likely includes affiliates [A]. If over, even internal production use and end-user-facing output need a paid license.
2. **Is our use "Non-Commercial"?** Personal project on company hardware/time, or eventual commercial app, may fall outside s2.2(i).
3. **LoRA / fine-tune rights:** ownership, distribution, and s3.5 transfer limits for any LoRA we train (incl. artist likeness LoRAs).
4. **Gemma terms:** the 2.5 text encoder is a Gemma 4 fine-tune bundled in the LTX repo; README says LTX-2.3's Gemma 3 "stays under Google's license". Whether Google Gemma terms (and its prohibited-use policy) also apply to the bundled Gemma 4 encoder and E2B enhancer (`Comfy-Org/gemma-4`) was **not confirmed** — needs review. [A]
5. **AUP review** and update cadence (version at time of use governs).
6. **Watermark/provenance obligations** for videos we publish; whether our pipeline (ComfyUI, re-encode, remux) preserves required marks.
7. **Music/likeness rights** for input songs and performer images — separate from LTX license, but central to a music-video app.
8. "More permissive licensing" claim in docs **[V]** overview page — confirm actual differences vs. LTX-2 Community License (LICENSE-2).
