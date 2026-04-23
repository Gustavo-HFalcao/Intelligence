---
name: voice-agent-error-recovery
description: "Guidelines for handling dirty voice inputs, Whisper hallucinations, and malformed audio logic."
---

# Voice Agent Error Recovery

Voice inputs are notoriously unreliable (background noise, accents, ambiguous terms). The agent must not blindly feed Whisper outputs into a database transaction.

## 1. Zero-Trust Inputs
Treat all transcribed JSON or text as potentially harmful or nonsensical (e.g. "Dez" vs "Test").

## 2. Validation Pipelines
Before submitting to Supabase, run a sanity check on extracted numbers and categories (via regex, strict LLM structuring, or Python Pydantic). If a value is missing or absurd, interrupt the workflow.

## 3. Fallback UX Prompts
Instead of crashing or saving "NaN", update the Reflex state with a polite error: *"Não consegui entender o valor financeiro. Você disse R$ 50 ou R$ 500?"*, allowing the user to correct the specific field manually.
