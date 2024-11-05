import spacy
from collections import Counter

# 加载 spaCy 的小型英文模型
nlp = spacy.load("en_core_web_sm")

# 示例文件列表
readme_files = ["README1.md"]  # 替换为你的文件路径

keywords = Counter()
for file_path in readme_files:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            doc = nlp(content)
            for token in doc:
                if token.is_alpha and not token.is_stop:  # 过滤停用词
                    keywords[token.lemma_.lower()] += 1
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")

print("Top keywords from README files:", keywords.most_common(10))
