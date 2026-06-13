---
name: documenting-meetings
description: Converts scattered meeting data (recordings, handwritten notes, diagrams, digital notes, supplementary documents) into a structured MS Word deliverable with summary, decisions, action items, open questions, and follow-up message. Use when the user mentions meeting notes, meeting summary, meeting minutes, action items from meeting, meeting documentation, or needs to consolidate meeting materials.
---

# Meeting Documentation

Converts scattered meeting materials—audio/video recordings, handwritten notes, diagrams, digital notes, and supplementary documents—into a single, well-formatted MS Word document containing a concise summary, decisions, action items with owners and due dates, open questions, and a ready-to-send follow-up message.

It is designed to run in **Claude Desktop** with:
- An MCP **filesystem** server (for listing/reading files and folders)
- An MCP **gaik-transcriber** server (for transcribing audio/video recordings)

## When to Use

Use this skill when:
- User mentions "meeting notes", "meeting summary", "meeting minutes", "meeting documentation"
- User needs to consolidate multiple meeting materials into one document
- User asks to extract action items, decisions, or follow-ups from a meeting
- User has meeting recordings, handwritten notes, or other meeting artifacts to process
- User wants a structured deliverable from meeting data

## Inputs

**Required (at least one):**
- Meeting recordings (audio/video files) – transcribed using `gaik-transcriber:transcribe_audio`
- Handwritten notes (scanned images) – interpreted visually
- Digital notes (text files, markdown, etc.)
- Diagrams/sketches/figures (images)
- Comments or notes from multiple people

**Optional:**
- Supplementary documents (PowerPoint slides, PDF guidelines, policy documents, Excel files)
- Output template (blank .docx with predefined headers, sections, logos, etc.)
- Sample output document (.docx or .pdf) defining style, format, tone, and length to follow

**Required parameter:**
- `input_folder`: Path to the main input folder containing the required subfolder structure. If not provided, ask the user to specify it.

**Required folder structure:**
```
<input_folder>/
├── input_documents/     # Required: recordings, photos, notes, presentations, PDFs, etc.
├── templates/           # Optional: blank template with predefined headers, sections, logos
└── sample_documents/    # Optional: sample document defining style, format, tone, length
```

## Tooling Rules (Windows vs Linux Path Safety)

### Why this matters
On Windows, Claude Desktop + toolchains sometimes behave like they are in a POSIX shell, producing paths like `/mnt/c/...`.
Meanwhile, your MCP servers may run **native Windows Python**, expecting `C:\...`.
This mismatch can cause “file not found” or failing shell commands.

### Strict rules
1) **Prefer MCP filesystem tools for file/folder operations**
Use the filesystem server for listing and reading files instead of shell commands.

2) **Avoid bash commands on Windows**
If you must run a command on Windows, prefer **PowerShell**.

3) **When calling gaik-transcriber, prefer Windows drive-letter paths on Windows**
Pass file paths like `C:\Users\...\recording.m4a`.
If you only have a POSIX/WSL path (e.g., `/mnt/c/...`), convert it to a Windows path before calling the transcriber, or rely on the transcriber server’s internal normalization (recommended).

4) **Never assume the environment is Linux**
Treat the runtime as OS-ambiguous and enforce the above rules to stay stable.

5) **Never do the following:**
NEVER run pip install, python -c, pdfplumber, or any ad-hoc parsing code for .pdf/.pptx/.xlsx.

NEVER use /mnt/user-data/uploads/... paths; only use paths returned by the MCP filesystem listing or the user-provided Windows folder.

If you are about to do any of the above, STOP and switch to the built-in PDF/PPTX/XLSX skills.

## Workflow

### Step 0 — Collect context
Ask (only if not provided):
- Meeting title or purpose (optional)
- Desired output format (Markdown is default)
- Any special focus: “only action items”, “only decisions”, “customer-facing summary”, etc.

## Step 1 — Validate input folder structure and capabilities

If the user has not specified an input folder path, ask for it and confirm it contains `input_documents/` (required).

### 1) Validate folder structure (MCP filesystem only)
Use the filesystem MCP tool to list:
- `<input_folder>`
- `<input_folder>\input_documents` (required)
- `<input_folder>\templates` (optional)
- `<input_folder>\sample_documents` (optional)

If `input_documents/` is missing or empty, stop and ask the user to add the meeting artifacts there.

### 2) Capability check (prevents Windows/Linux path loops for binaries)
Purpose: decide upfront whether this environment can process **binary** files from a Windows folder without requiring the user to upload them.

Inventory binary files found in:
- `<input_folder>\input_documents`
- `<input_folder>\templates`
- `<input_folder>\sample_documents`

Treat the following as **binary** (not safely readable via text tools):
- `.pdf`, `.pptx`, `.xlsx`, `.docx`

Decision:
- If ANY binary files exist and are ONLY in the Windows folder:
  - Assume you cannot process them directly unless you have a binary-capable tool.
  - The official Node filesystem MCP server supports reading text files and reading image/audio media, but does not guarantee generic binary reads for Office/PDF files. :contentReference[oaicite:2]{index=2}
  - Therefore:
    - If a dedicated MCP document-parser tool is available (recommended), use it for these files.
    - Otherwise, you MUST ask the user to upload/attach these binaries in Claude Desktop to process them with built-in PDF/PPTX/XLSX/DOCX skills.

If the user asks for “local-folder only” processing of PDF/PPTX/XLSX/DOCX:
- Explain that this requires either:
  - a binary-capable filesystem MCP server (supports base64/binary reads), or
  - a Windows-native document-parser MCP server.
  (Example of a filesystem MCP server that explicitly supports binary/base64 reads: `mark3labs/mcp-filesystem-server`.) :contentReference[oaicite:3]{index=3}

Continue with the core workflow (transcription + text notes + images) regardless of the binary handling outcome.

### Step 2 — Inventory input files
From `input_documents/`, create a quick inventory:
- Recordings (audio/video)
- Images (handwritten notes, diagrams)
- Text documents (agenda, minutes draft, emails, etc.)
- PDFs / slides (read text if possible; otherwise summarize)

### Step 3 — Transcribe recordings (gaik-transcriber MCP tool)
For each audio/video file, call:

- `gaik-transcriber:transcribe_audio`
  - `file_path`: full path to the recording
  - `enhanced`: false by default (true only if user asks for enhanced quality)

If transcription fails with “file not found”:
- Re-check the path style and ensure Windows drive-letter paths on Windows.

#### Step 4 - Images (Handwritten Notes, Diagrams, Sketches, Figures)
For each image file (.jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff):
2. Interpret the image content (handwritten notes, diagrams, figures)
3. Create a textual description capturing all relevant information

#### Step 5 - Notes
Read files directly (.txt, .md, .rtf).
Use /mnt/skills/public/docx/SKILL.md for reading/writing .docx files.

## Step 6 — Supplementary documents (.pdf, .pptx, .xlsx, .docx)

Goal: extract relevant information from supplementary documents WITHOUT ad-hoc parsing code and WITHOUT Windows/Linux path mismatches.

### Non-negotiables (hard rules)
- NEVER run `cp`, `pip install`, `python -c`, `pdfplumber`, `soffice`, `pandoc`, or any ad-hoc parsing commands to read `.pdf/.pptx/.xlsx/.docx` from Windows paths.
- NEVER assume `C:\...` or `/mnt/c/...` is accessible inside a Linux sandbox.
- NEVER invent upload paths (e.g., `/mnt/user-data/uploads/...`) unless the environment explicitly provides them.
- Do not use the filesystem MCP server to “load built-in skill files.” The filesystem server is for user-allowed directories, not Claude’s internal skill library. (Use built-in skills directly when attachments are available.) :contentReference[oaicite:4]{index=4}

### Decision tree

A) If the supplementary file is uploaded/attached in Claude Desktop
- Use the corresponding built-in skill:
  - `.pdf` → PDF skill
  - `.pptx` → PPTX skill
  - `.xlsx` → XLSX skill
  - `.docx` → DOCX skill
- Extract only relevant content for the meeting deliverable (decisions, timelines, roadmap items, action items, risks).
- Attribute extracted content by filename.

B) If the supplementary file is ONLY present in the Windows folder (discovered via `filesystem:list_directory`)
1) Text-like files (`.txt`, `.md`, `.csv`, `.json`)
- Read via filesystem `read_text_file` and extract relevant content.

2) Binary files (`.pdf`, `.pptx`, `.xlsx`, `.docx`) — IMPORTANT
- Do NOT attempt conversion or parsing via sandbox tools (pandoc/python/soffice/etc.).
- If a dedicated MCP document-parser tool is available:
  - Call the parser using the Windows path and use returned extracted text/tables in synthesis.
- Otherwise:
  - Ask the user to upload/attach the file(s) in Claude Desktop.
  - Continue processing what you can (transcripts, notes, images) and list the missing binaries under “Missing inputs”.

Template + samples:
- If templates/sample documents are `.docx/.pdf/.pptx/.xlsx` and are only on Windows disk:
  - Ask the user to upload them.
  - If not provided, proceed with a clean default Markdown structure.

### Output handling
- If supplementary binaries are unavailable (not uploaded, and no parser tool), clearly list them:
  - Missing inputs: `<filename1>`, `<filename2>`, ...
- Produce the meeting deliverable using available evidence and a default format.
- Do not block the entire workflow just because supplementary binaries are missing.

### Step 7: Fuse Information

Combine all processed inputs into a single consolidated text block with clear separators:

```
=== TRANSCRIPTION: <filename> ===
<transcribed content>

=== HANDWRITTEN NOTES: <filename> ===
<interpreted content>

=== DIGITAL NOTES: <filename> ===
<note content>

=== DIAGRAM/FIGURE: <filename> ===
<description of diagram/figure>

=== SUPPLEMENTARY: <filename> ===
<extracted content>
```
### Step 8: Check for Template and Sample Documents

Check the dedicated subfolders for template and sample:

**Template (`<input_folder>/templates/`):**
- Look for a blank .docx file with predefined structure (headers, sections, logos)
- If multiple files exist, use the first .docx file found

**Sample (`<input_folder>/sample_documents/`):**
- Look for a .docx or .pdf file defining the required style, format, tone, and length
- If multiple files exist, use the first document found

If found:
- For template: Copy it and fill in the content (do not modify structure)
- For sample: STRICTLY follow its format, style, tone, and length

### Step 9: Generate the Deliverable

Read the docx skill before creating the document:
```
view /mnt/skills/public/docx/SKILL.md
```

Then follow the docx skill's "Creating a new Word document" workflow to generate the output.

**If template provided:** Copy the template and fill in sections according to the template structure.

**If no template:** Create a new document using the output format below.

### Step 10: Save and Present

1. Save the document to the `input_documents` folder
2. Use `present_files` to share with the user

## Output Format (FLEXIBLE - adapt if template/sample provided)

When no template or sample is provided, use this structure:

```
MEETING SUMMARY
===============

Date: [extracted or inferred date]
Attendees: [if identifiable from inputs]
Duration: [if available]

---

EXECUTIVE SUMMARY
-----------------
[2-4 paragraph concise summary of the meeting covering main topics discussed, 
key points, and overall outcomes. Keep factual, based only on input content.]

---

DECISIONS MADE
--------------
1. [Decision text]
   - Context: [brief context if available]
   
2. [Decision text]
   - Context: [brief context if available]

[If no decisions found in inputs, OMIT this section entirely]

---

ACTION ITEMS
------------
| # | Action Item | Owner | Due Date | Priority |
|---|-------------|-------|----------|----------|
| 1 | [description] | [name] | [date] | [H/M/L] |
| 2 | [description] | [name] | [date] | [H/M/L] |

[If owner/due date not specified in inputs, mark as "TBD"]
[If no action items found, OMIT this section entirely]

---

OPEN QUESTIONS
--------------
1. [Question that was raised but not resolved]
2. [Question requiring follow-up]

[If no open questions found, OMIT this section entirely]

---

FOLLOW-UP MESSAGE
-----------------
[Ready-to-paste message for email or chat, summarizing key outcomes and next steps. 
Keep professional and concise. Format as:]

Subject: Meeting Follow-up - [Topic/Date]

Hi team,

[1-2 paragraphs summarizing the meeting, key decisions, and action items]

Next steps:
- [Action item 1] - [Owner] by [Date]
- [Action item 2] - [Owner] by [Date]

Please let me know if you have any questions.

Best regards,
[Sender placeholder]
```

## Guardrails

**Do:**
- Extract information faithfully from provided inputs
- Mark uncertain information as "TBD" or "unclear from recording"
- Preserve original terminology and names from the inputs
- STRICTLY follow template/sample format when provided
- Omit sections if no relevant information exists in inputs

**Do NOT:**
- Invent or hallucinate any information not present in inputs
- Add action items, decisions, or attendees not mentioned in source materials
- Make assumptions about dates, owners, or deadlines not explicitly stated
- Include sections in the deliverable if the information is not in the inputs

**If information is missing:**
- For required fields: Mark as "TBD" or "Not specified in meeting materials"
- For entire sections: Omit the section from the deliverable
- If critical inputs are missing: Inform the user what additional materials would help

**Error handling:**
- If transcription fails: Report the error and continue with other inputs
- If a file cannot be parsed: Log the issue and proceed with remaining files
- If no usable inputs found: Ask the user to verify the folder path and file formats

## Examples

### Example 1: Standard Meeting with Recording and Notes

**User prompt:**
"Process my meeting materials from /home/user/meetings/q4-planning and create a summary document"

**Expected folder structure:**
```
/home/user/meetings/q4-planning/
├── input_documents/
│   ├── meeting-recording.mp4
│   ├── whiteboard-photo.jpg
│   └── my-notes.txt
├── templates/           # (empty or absent)
└── sample_documents/    # (empty or absent)
```

**Expected behavior:**
1. Validates folder structure, finds input_documents/ with 3 files
2. Transcribes recording using gaik-transcriber
3. Interprets whiteboard photo
4. Reads digital notes
5. Fuses all content with separators
6. Generates Word document with all applicable sections (no template/sample)
7. Saves to outputs and presents to user

### Example 2: With Template and Sample

**User prompt:**
"Create meeting minutes from the files in /meetings/standup using our company template"

**Expected folder structure:**
```
/meetings/standup/
├── input_documents/
│   ├── recording.m4a
│   └── notes.txt
├── templates/
│   └── company-template.docx
└── sample_documents/
    └── sample-minutes.docx
```

**Expected behavior:**
1. Finds template in templates/ subfolder
2. Finds sample in sample_documents/ subfolder
3. Processes all materials in input_documents/
4. Copies template and fills in content following sample's style
5. Presents formatted document

### Example 3: Minimal Inputs

**User prompt:**
"I just have a voice memo from our call - can you turn it into meeting notes? The folder is /recordings/client-call"

**Expected folder structure:**
```
/recordings/client-call/
├── input_documents/
│   └── voice-memo.m4a
├── templates/           # (empty or absent)
└── sample_documents/    # (empty or absent)
```

**Expected behavior:**
1. Validates structure, finds single audio file in input_documents/
2. Transcribes the audio file
3. Generates deliverable with available sections only
4. Omits sections where no information exists
5. Notes in follow-up message that details may need verification

## References
Following these reference documents for detailed handing for each input file type, and guidance on each deliverable section. 
- `reference/INPUT_FORMATS.md` – Detailed handling for each input file type
- `reference/OUTPUT_SECTIONS.md` – Guidance on each deliverable section
