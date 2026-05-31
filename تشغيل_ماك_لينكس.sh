#!/bin/bash
echo "جارٍ تشغيل مصحح البابل شيت..."
pip3 install opencv-python numpy Pillow -q
python3 omr_grader.py
