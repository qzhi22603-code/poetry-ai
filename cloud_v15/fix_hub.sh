#!/bin/bash
pip install -q "huggingface_hub==0.36.0" -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "import huggingface_hub; print('hub ver:', huggingface_hub.__version__)"
