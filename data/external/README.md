# External data

`metaqa/` is not committed. It holds MetaQA (Zhang, Dai, Kozareva, Smola, Song: "Variational Reasoning for Question
Answering with Knowledge Graph", AAAI 2018), downloaded from https://github.com/yuyuz/MetaQA — the vanilla `kb.txt`
and the 1-, 2- and 3-hop `qa_dev` / `qa_test` files with their `qtype` files, all in one folder with the hop written
in front of the name. The dataset is released under a Creative Commons licence (its `LICENSE.txt` is in the folder).

`metaqa.manifest.json` pins every file's line count and sha256 and says which hop and split it is.
`uv run python -m trailmend.metaqa.files` checks a download against it.
