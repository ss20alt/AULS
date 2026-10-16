#!/bin/bash
cd /c/Users/acer/Documents/lilinatest/studio
for p in auto_split_leite:PANTALLA_DIVIDIDA:leite auto_headline_propuestas:TITULARES:propuestas auto_report_calma:REPORTAJE:calma; do
  IFS=: read name label ang <<< "$p"
  PYTHONIOENCODING=utf-8 python build.py $name > projects/$name/rerender.log 2>&1
  PYTHONIOENCODING=utf-8 python qa.py $name > projects/$name/qa_run.log 2>&1
  cp projects/$name/$name.mp4 /c/Users/acer/Downloads/Lilian_AUTO_${label}_${ang}_1min.mp4
  cp projects/$name/${name}_liviano.mp4 /c/Users/acer/Downloads/Lilian_AUTO_${label}_${ang}_1min_liviano.mp4
  echo "OK $name"
done
