# Evaluation Prompts

Test prompts for validating the documenting-meetings skill.

---

## Eval 1: Standard Multi-Input Processing

**Prompt:**
"I have a bunch of meeting materials in /home/user/meetings/standup - there's a recording, some photos of the whiteboard, and my typed notes. Can you turn these into proper meeting minutes?"

**Folder structure needed:**
```
/home/user/meetings/standup/
├── input_documents/
│   ├── meeting.mp4
│   ├── whiteboard1.jpg
│   ├── whiteboard2.jpg
│   └── notes.txt
├── templates/           # (empty)
└── sample_documents/    # (empty)
```

**Pass Criteria:**
- Validates folder structure before processing
- Finds and processes files in input_documents/ subfolder
- Calls `gaik-transcriber:transcribe_audio` MCP tool for transcribing an audio/video file
- Views and interprets both image files
- Reads the text notes file
- Creates fused content with clear separators between sources
- Generates Word document with applicable sections
- Saves to the same folder (`input_documents`) as the input folder and presents file
- Does NOT include sections for which no information exists

**Failure Modes:**
- Looks for files in root folder instead of `input_documents/`
- Skips the transcription step
- Ignores image files
- Invents action items or decisions not in source materials
- Includes empty sections with placeholder text
- Fails to present the final file

---

## Eval 2: Template and Sample Handling

**Prompt:**
"Use our company template to create meeting notes from the materials in /meetings/quarterly-review. There's also a sample from last quarter showing how we like them formatted."

**Folder structure needed:**
```
/meetings/quarterly-review/
├── input_documents/
│   ├── recording.m4a
│   └── slides.pptx
├── templates/
│   └── company-template.docx
└── sample_documents/
    └── sample-q3-notes.docx
```

**Pass Criteria:**
- Validates folder structure
- Finds template in templates/ subfolder
- Finds sample in sample_documents/ subfolder
- Processes files in input_documents/ (recording and slides)
- Copies the template (doesn't create from scratch)
- Analyzes sample for style, tone, and length
- Fills template following sample's format
- Preserves template's logos and headers
- Final document matches sample's structure and tone

**Failure Modes:**
- Ignores templates/ subfolder and creates new document
- Ignores sample_documents/ subfolder
- Looks for template/sample in input_documents/
- Corrupts template formatting
- Mixes template with default output format

---

## Eval 3: Minimal Input (Audio Only)

**Prompt:**
"I just have a voice memo from our client call - can you create notes from it? The folder is /recordings/client-sync"

**Folder structure needed:**
```
/recordings/client-sync/
├── input_documents/
│   └── client-sync.m4a
├── templates/           # (empty or absent)
└── sample_documents/    # (empty or absent)
```

**Pass Criteria:**
- Handles single-file input gracefully
- Correctly locates file in `input_documents/` subfolder
- Successfully transcribes the audio
- Creates Word document with available sections only
- Omits sections where information not present (e.g., no explicit decisions = no Decisions section)
- Follow-up message adapts to limited information
- Acknowledges any limitations in the output

**Failure Modes:**
- Fails without multiple inputs
- Looks for audio file in root folder
- Invents content to fill all sections
- Includes empty sections with "None" or "N/A"
- Produces generic boilerplate unrelated to actual content

---

## Eval 4: Error Recovery

**Prompt:**
"Process the meeting files in /meetings/team-sync"

**Folder structure needed:**
```
/meetings/team-sync/
├── input_documents/
│   ├── meeting.mp4       # (corrupted or unreadable)
│   ├── notes.md
│   └── diagram.png
├── templates/           # (empty)
└── sample_documents/    # (empty)
```

**Pass Criteria:**
- Validates folder structure correctly
- Attempts transcription and handles failure gracefully
- Reports the transcription error clearly
- Continues processing other valid files in input_documents/
- Generates document from available content
- Notes in output that transcription failed

**Failure Modes:**
- Crashes on transcription failure
- Abandons all processing after one error
- Silent failure (produces document without mentioning issue)
- Claims transcription succeeded when it didn't

---

## Eval 5: Missing Input Folder

**Prompt:**
"Create meeting notes from my last team meeting"

**Pass Criteria:**
- Recognizes no folder path provided
- Asks user for the folder path
- Explains required folder structure (input_documents/, templates/, sample_documents/)
- Does NOT guess or assume a path
- Proceeds correctly once valid path with correct structure is provided

**Failure Modes:**
- Attempts to process without valid path
- Makes up a folder path
- Does not explain the required subfolder structure
- Crashes or produces error without guidance

---

## Eval 6: Complex Excel and Supplementary Documents

**Prompt:**
"I need meeting minutes from our budget review. The materials are in /finance/budget-review including the spreadsheet we discussed and the policy document."

**Folder structure needed:**
```
/finance/budget-review/
├── input_documents/
│   ├── discussion.mp3
│   ├── budget-2024.xlsx
│   ├── expense-policy.pdf
│   └── notes.txt
├── templates/           # (empty)
└── sample_documents/    # (empty)
```

**Pass Criteria:**
- Validates folder structure
- Processes all files in input_documents/
- Transcribes audio
- Reads and interprets all sheets in Excel file
- Extracts text from PDF document
- Synthesizes information from all sources
- References specific data from Excel when relevant to meeting content
- Does not include irrelevant details from supplementary docs

**Failure Modes:**
- Ignores Excel file
- Includes entire Excel content verbatim
- Fails to extract PDF text
- Loses connection between supplementary docs and meeting discussion
- Looks for files in wrong folder

---

## Notes for Testing

### Test Environment Setup
1. Create test folders with the required subfolder structure:
   ```
   <test_folder>/
   ├── input_documents/   # Place test files here
   ├── templates/         # Place template here (if testing)
   └── sample_documents/  # Place sample here (if testing)
   ```
2. Ensure `gaik-transcriber` MCP server is running
3. Have sample template and sample output documents ready for Eval 2

### Model-Specific Considerations
- **Haiku**: May need simpler prompts; verify all steps are followed
- **Sonnet**: Expected primary model; full workflow should execute
- **Opus**: Test with complex multi-file scenarios

### Common Issues to Watch
- Failure to call gaik-transcriber (critical for audio processing)
- Looking for files in root folder instead of input_documents/
- Looking for template/sample in input_documents/ instead of their subfolders
- Inventing content not in source materials
- Including empty sections instead of omitting them
- Not using template when provided
- Forgetting to present final file to user
