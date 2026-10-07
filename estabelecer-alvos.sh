#!/bin/bash
# criar lista de projetos
echo ""> "projetos-alvo-testes.txt"
for i in "job-outreach" "suuid-v2" "yb-convenio" "WA-Keeper" "Shameless"; do
  echo $i
  echo "--------------------------------------------------"
  d=$(find ~/Sync/Projects/ -type d -name $i -print -quit 2>/dev/null)
  echo $d
  echo $d >> "projetos-alvo-testes.txt"
done
