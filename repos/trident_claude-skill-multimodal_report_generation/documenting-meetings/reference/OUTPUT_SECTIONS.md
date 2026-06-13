# Output Sections Reference

Guidance on crafting each section of the meeting deliverable.

## Contents
- Section Overview
- Executive Summary
- Decisions Made
- Action Items
- Open Questions
- Follow-Up Message
- Handling Missing Information

---

## Section Overview

| Section | Required | When to Include |
|---------|----------|-----------------|
| Header (Date, Attendees) | Yes | Always |
| Executive Summary | Yes | Always (even if brief) |
| Decisions Made | No | Only if decisions found in inputs |
| Action Items | No | Only if action items found in inputs |
| Open Questions | No | Only if unresolved questions found |
| Follow-Up Message | Yes | Always |

**Key principle:** Never invent content. If information for a section doesn't exist in the inputs, omit the entire section.

---

## Executive Summary

### Purpose
Provide a concise overview of what was discussed and accomplished in the meeting.

### Content Requirements
- 2-4 paragraphs maximum
- Factual and objective tone
- Cover main topics in order of importance
- Mention key outcomes without duplicating other sections

### What to Include
- Meeting purpose/context (if stated)
- Main topics discussed
- High-level outcomes
- Any significant concerns raised

### What to Avoid
- Detailed action items (these go in their section)
- Verbatim quotes (unless critical)
- Speculation or interpretation beyond source material

### Example
```
The Q4 planning meeting focused on budget allocation and product roadmap 
prioritization. The team reviewed three major initiatives: the customer 
portal redesign, API modernization, and mobile app launch.

Discussion centered on resource constraints, with particular attention 
to the engineering team's capacity through the holiday season. Several 
trade-offs were evaluated regarding timeline versus feature scope.

The team aligned on a phased approach, with the portal redesign taking 
priority due to customer commitments. Mobile app launch was deferred 
to Q1 pending additional headcount.
```

---

## Decisions Made

### Purpose
Document explicit decisions reached during the meeting.

### Identification Signals
Look for phrases in the input like:
- "We decided..."
- "The decision is..."
- "We agreed to..."
- "It was concluded that..."
- "Going forward, we will..."
- "The final call is..."

### Format
```
1. [Clear statement of decision]
   - Context: [Brief background if available]
   
2. [Clear statement of decision]
   - Context: [Brief background if available]
```

### What Qualifies as a Decision
- Explicit agreement on a course of action
- Selection between alternatives
- Approval or rejection of a proposal
- Commitment to a timeline or approach

### What Does NOT Qualify
- Discussion of options (without resolution)
- Tentative plans pending approval
- Individual opinions
- Topics for future consideration

### When to Omit
If no explicit decisions were made during the meeting, omit this section entirely. Do not create placeholder text like "No decisions were made."

---

## Action Items

### Purpose
Capture tasks that need to be completed, with ownership and deadlines.

### Identification Signals
Look for phrases like:
- "[Name] will..."
- "Action: [task]"
- "TODO: [task]"
- "Next step: [task]"
- "Assigned to [name]"
- "By [date], we need to..."
- "Follow up on..."

### Table Format
```
| # | Action Item | Owner | Due Date | Priority |
|---|-------------|-------|----------|----------|
| 1 | [description] | [name] | [date] | [H/M/L] |
```

### Field Handling

**Action Item:**
- Write as specific, actionable task
- Start with action verb
- Include enough context to be standalone

**Owner:**
- Use name exactly as mentioned in inputs
- If multiple owners: "[Name1], [Name2]"
- If unclear: "TBD"

**Due Date:**
- Use date format from inputs
- If relative ("next week"): Convert to actual date if current date known
- If not specified: "TBD"

**Priority:**
- H (High): Blocking other work, urgent
- M (Medium): Important but not urgent
- L (Low): Nice to have
- If not indicated: Leave blank or mark "TBD"

### When to Omit
If no action items were assigned during the meeting, omit this section entirely.

---

## Open Questions

### Purpose
Capture questions that were raised but not resolved during the meeting.

### Identification Signals
- Questions explicitly deferred
- Unresolved debates
- Items needing external input
- Pending research or investigation
- "We need to figure out..."
- "The question is..."
- "TBD on..."

### Format
```
1. [Question as clear statement]
   - Assigned to: [name, if any]
   
2. [Question as clear statement]
```

### What Qualifies
- Explicit unresolved questions
- Topics requiring further investigation
- Decisions pending additional information
- Items deferred to future meetings

### When to Omit
If all raised questions were resolved, omit this section entirely.

---

## Follow-Up Message

### Purpose
Provide a ready-to-paste message for email or chat distribution.

### Structure
```
Subject: Meeting Follow-up - [Topic/Date]

Hi team,

[Opening: 1 sentence on meeting purpose/context]

[Body: 1-2 paragraphs summarizing key points]

[If decisions made:]
Key decisions:
- [Decision 1]
- [Decision 2]

[If action items assigned:]
Action items:
- [Action 1] - [Owner] by [Date]
- [Action 2] - [Owner] by [Date]

[If open questions:]
Open items:
- [Question 1]

[Closing: Next meeting or general sign-off]

Best regards,
[Sender placeholder]
```

### Tone Guidelines
- Professional but approachable
- Concise—aim for readable in under 1 minute
- Focus on outcomes and next steps
- Avoid meeting play-by-play

### Customization
- Adapt formality based on sample document if provided
- Use team's typical salutations if discernible
- Include recipient group if mentioned ("Hi Marketing Team,")

---

## Handling Missing Information

### Principle
**Never invent information.** All content must be traceable to input materials.

### Missing Attendees
If not identifiable:
```
Attendees: [Not specified in meeting materials]
```

### Missing Dates
If meeting date not determinable:
```
Date: [To be confirmed]
```

### Missing Owners for Action Items
```
| 1 | Complete budget review | TBD | 2024-01-15 | M |
```

### Missing Due Dates
```
| 1 | Complete budget review | Sarah | TBD | M |
```

### Partial Information
If only some information is available, include what exists:
```
Attendees: John, Sarah, and others (full list not captured)
```

### Conflicting Information
If inputs contain contradictions:
1. Note the discrepancy
2. Present both versions
3. Mark for verification

```
Note: Meeting date appears as both Dec 15 and Dec 16 in notes. 
Please verify and correct.
```
