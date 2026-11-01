#!/bin/bash
pip install -q "transformers==4.51.3" "peft==0.15.2" "accelerate==1.6.0" "bitsandbytes==0.45.5" "huggingface_hub==0.36.0" -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "import torch, transformers, peft, bitsandbytes as bnb; print('torch', torch.__version__, '| tf', transformers.__version__, '| peft', peft.__version__, '| bnb', bnb.__version__)"
