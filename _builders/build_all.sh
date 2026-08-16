#!/usr/bin/env bash
# Regenerate every derived artifact from its single source of truth.
# Run from the repository root:  bash _builders/build_all.sh
set -e
cd "$(dirname "$0")/.."

echo "== labs: starters + notebooks from solutions =="
python3 _builders/build_labs.py

echo
echo "== decks =="
node _builders/build_deck.js content_program.js  00_Program/Day0_Programme_Kickoff_Deck.pptx
node _builders/build_deck.js content_day1.js     Day1_Foundations/Day1_Foundations_Deck.pptx
node _builders/build_deck.js content_day2.js     Day2_RAG/Day2_RAG_Deck.pptx
node _builders/build_deck.js content_day3.js     Day3_Governance/Day3_Governance_Deck.pptx
node _builders/build_deck.js content_capstone.js Capstone/Capstone_Deck.pptx

echo
echo "== facilitation guides =="
node _builders/build_guide.js content_program.js  00_Program/Day0_Kickoff_Facilitation_Guide.docx  "Day 0 Kickoff"
node _builders/build_guide.js content_day1.js     Day1_Foundations/Day1_Facilitation_Guide.docx "Day 1"
node _builders/build_guide.js content_day2.js     Day2_RAG/Day2_Facilitation_Guide.docx        "Day 2"
node _builders/build_guide.js content_day3.js     Day3_Governance/Day3_Facilitation_Guide.docx "Day 3"
node _builders/build_guide.js content_capstone.js Capstone/Capstone_Facilitation_Guide.docx    "Capstone"

echo
echo "== reference documents (markdown -> Word) =="
node _builders/build_doc.js 00_Program/LAB_ENVIRONMENT_GUIDE.md    00_Program/Lab_Environment_Guide.docx      "How to Run the Labs"
node _builders/build_doc.js 00_Program/CURRICULUM_GAP_ANALYSIS.md  00_Program/Curriculum_Gap_Analysis.docx    "Curriculum & Specification Gap Analysis"
node _builders/build_doc.js Capstone/docs/BUILD_GUIDE.md           Capstone/docs/Capstone_Build_Guide.docx    "Capstone Build Guide"

echo
echo "== governance register =="
python3 _builders/build_register.py

echo
echo
echo "== validation =="
python3 _builders/validate_labs.py

echo
echo "Done. Now run: python3 00_Program/verify_environment.py"
