import spacy

# 加载预训练的模型
nlp = spacy.load("en_core_web_sm")

# 要分析的文本
text = "West Hartford, CT"

# 处理文本
doc = nlp(text)

# 提取地理位置
locations = []
for ent in doc.ents:
    if ent.label_ == "GPE":  # GPE 表示地理政治实体
        locations.append(ent.text)

print("Recognized locations:", locations)