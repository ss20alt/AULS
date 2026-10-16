#!/bin/bash
cd /c/Users/acer/Documents/lilinatest/studio
PYTHONIOENCODING=utf-8 python make_video.py --style headline --angle propuestas
PYTHONIOENCODING=utf-8 python make_video.py --style ink --angle leite
for p in auto2_fx_sistema auto2_ink_leite auto2_report_prensa auto2_headline_propuestas auto2_news_calma auto2_call_prensa auto2_split_calma; do
  echo "QA $p"; PYTHONIOENCODING=utf-8 python qa.py $p 2>/dev/null | sed -n '/HALLAZGOS/,$p'
done
echo FIN
