# Fix README Architecture Diagram

## Job To Be Done
Fix the ASCII box-drawing alignment in the "Architecture (L0 Core)" diagram so the Beads (bd) box renders with a uniform right edge on GitHub.

## Requirements
- The right-side `│` characters of the Beads (bd) box must align vertically on every line
- The box width must be consistent between the top `┌───...───┐` border, all content lines, and the bottom `└───...───┘` border
- The diagram must render correctly in GitHub's markdown code block (monospace font)
- The left AI Agent box alignment must also be verified/preserved

## Constraints
- Only modify the code block in the "Architecture (L0 Core)" section of README.md
- Use Unicode box-drawing characters consistent with the existing diagram style
- Do not change the textual content inside the boxes, only fix spacing/alignment

## Notes
- Lines 374-385 of README.md contain the affected diagram
- The inner sub-boxes (┌───┐ for A, B, C nodes) use box-drawing characters that may have inconsistent padding relative to the outer box
- Previous commit `f8abbbd` attempted to fix diagram rendering issues but the Beads box right edge is still misaligned
