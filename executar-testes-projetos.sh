#!/bin/bash
# executar testes sobre projetos
if [ -z $1 ]; then
  echo "discover sources or analyze"
  exit 0
fi
for i in $(cat "projetos-alvo-testes.txt"); do
  echo $i
  echo "----------------------------------------------------------------------------------"
  .venv/bin/governancekit --development \
    --root $i \
    adoption $1
done