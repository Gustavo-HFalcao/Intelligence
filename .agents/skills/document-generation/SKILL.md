---
name: document-generation
description: "Generating business value documents (PDF, DOCX, PPTX) programmatically based on AI generated insights or analytical contexts."
license: MIT
metadata:
  date: March 2026
---

# Document Generation (PDF, PPTX, DOCX)

Agents should not just answer in a chat interface. They should produce highly tailored, professional business documents (like a Morning Briefing or a Financial Investigation Report) that users can download or email to executives.

## When to Apply
- When the user asks: "Save this analysis as a PDF".
- When a Proactive Agent prepares the weekly summary.

## Tooling and Approaches
1. **PDF Generation**
   - **Recommended Stack**: `ReportLab` (for complex logic) or HTML-to-PDF libraries like `WeasyPrint`.
   - **Best Practice**: Have the LLM Agent write Markdown. Use a Markdown-to-HTML parser, then feed that HTML into WeasyPrint with a pre-defined CSS template that matches the company branding (Bomtempo Dashboard colors).

2. **Word (DOCX) & PowerPoint (PPTX)**
   - **Recommended Stack**: `python-docx` and `python-pptx`.
   - **Best Practice**: DO NOT have the AI generate documents from scratch. Create an empty branded template (.docx or .pptx) inside the codebase first. Have the agent load the template, locate specific placeholders (e.g., `{{summary_text}}`, `{{chart_image}}`), inject the data, and save it as a new file.

3. **Storage Strategy**
   - **Rule**: Never pass binary document blobs directly to the UI through the Reflex state if they are large.
   - **Action**: Save the generated document into a Supabase Storage Bucket, generate a short-lived Signed URL, and return that URL format to the UI so the user can download it seamlessly.
