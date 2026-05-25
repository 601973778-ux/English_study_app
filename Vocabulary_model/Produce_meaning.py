import json
import re
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

def extract_pure_meaning(content):
    """
    仅从 content 文本中提取核心中文意思，不识别词性
    """
    # 提取模式：
    # 1. 匹配被引号包裹的中文内容
    # 2. 匹配在“意为”、“翻译为”等关键词后面的中文短语
    meaning_patterns = [
        r'["“]([^"”\s]*[\u4e00-\u9fa5]+[^"”\s]*)["”]', 
        r'(?:意为|翻译为|中文是|表示|译为|对应中文为|指的是|中文翻译是|直译为)[:：\s]*([ \u4e00-\u9fa5、，,]+)'
    ]

    results = []
    
    # 遍历所有可能的匹配模式
    for pattern in meaning_patterns:
        matches = re.findall(pattern, content)
        for m in matches:
            # 清洗提取出的文字：去除可能误抓的英文点号、空格等
            clean_m = re.sub(r'[a-zA-Z.．]', '', m).strip(' ，、；')
            # 确保提取到的是包含中文字符的内容且不重复
            if clean_m and any('\u4e00' <= char <= '\u9fa5' for char in clean_m):
                if clean_m not in results:
                    results.append(clean_m)
    
    # 如果通过关键词没找着，尝试抓取内容的第一句话（通常是释义）
    if not results:
        first_line = content.split('\n')[0]
        # 抓取第一行中可能存在的中文描述
        fallback = re.search(r'([\u4e00-\u9fa5、，]+)', first_line)
        if fallback:
            return fallback.group(1).strip(' ，、')
        return "（待人工校对）"
    
    # 用分号连接多个意思
    return "；".join(results)

def process_jsonl(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                content = data.get("content", "")
                
                # 提取纯意思
                meaning = extract_pure_meaning(content)
                
                # 插入新标签 Meaning
                data["Meaning"] = meaning
                
                # 写入新文件
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
            except Exception as e:
                print(f"处理行时出错: {e}")

if __name__ == "__main__":
    # 相对脚本目录，避免「在其他 cwd 下运行」导致找不到 words.jsonl
    input_filename = _SCRIPT_DIR / "words.jsonl"
    output_filename = _SCRIPT_DIR / "words_only_meaning.jsonl"

    if not input_filename.is_file():
        raise SystemExit(f"找不到输入文件: {input_filename}")

    print("正在处理文件，请稍候...")
    process_jsonl(input_filename, output_filename)
    print(f"处理完成！提取后的数据已保存至: {output_filename}")