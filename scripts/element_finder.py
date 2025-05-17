from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import re

def parse_html_content(content):
    """解析HTML内容，提取文本、属性值等"""
    text = ""
    attrs = {}
    
    # 提取标签名
    tag_match = re.search(r'<(\w+)[^>]*>', content)
    tag_name = tag_match.group(1) if tag_match else None
    
    # 提取属性
    attr_matches = re.finditer(r'(\w+)=\"([^\"]*)\"', content)
    for match in attr_matches:
        attrs[match.group(1)] = match.group(2)
    
    # 提取文本内容
    text_match = re.search(r'>([^<]+)<', content)
    if text_match:
        text = text_match.group(1).strip()
    
    # 提取onclick中的URL部分（如果存在）
    if 'onclick' in attrs and 'index2.php' in attrs['onclick']:
        url_match = re.search(r"'(index2\.php[^']+)'|\"(index2\.php[^\"]+)\"", attrs['onclick'])
        if url_match:
            attrs['target_url'] = url_match.group(1) or url_match.group(2)
    
    print(f"解析HTML内容: 标签={tag_name}, 文本={text}, 属性={attrs}")
    return tag_name, text, attrs

def build_xpath(tag_name, text, attrs, is_container=False):
    """构建XPath表达式"""
    conditions = []
    
    if tag_name:
        xpath_base = f".//{tag_name}" if not is_container else f"//{tag_name}"
    else:
        xpath_base = ".//*" if not is_container else "//*"
    
    # 优先使用文本内容匹配，这通常是最可靠的
    if text:
        conditions.append(f"contains(text(),\"{text}\")")
    
    # 如果有提取的target_url，优先使用它来匹配
    if 'target_url' in attrs:
        conditions.append(f"contains(@onclick,\"{attrs['target_url']}\")")
        # 移除target_url，避免后续重复处理
        del attrs['target_url']
    
    # 对于href和class等常见属性，使用精确匹配
    for attr, value in attrs.items():
        if value and attr in ['href', 'class', 'id', 'name', 'type', 'value']:
            if "'" in value:
                # 使用concat函数处理包含单引号的属性值
                parts = [f"'{part}'" for part in value.split("'")]
                conditions.append(f"@{attr}=concat({','.join(parts)})")
            else:
                conditions.append(f"@{attr}=\"{value}\"")
        # 对于onclick等复杂属性，使用简化的contains匹配
        elif value and attr == 'onclick':
            # 只匹配函数名部分，避免复杂的URL匹配
            if 'RA_UseBack' in value:
                conditions.append(f"contains(@{attr},'RA_UseBack')")
            else:
                # 如果没有特定函数名，则使用contains匹配值的一小部分
                conditions.append(f"contains(@{attr},\"{value[:15]}\")")
    
    # 如果条件太多可能导致匹配过于严格，保留最重要的几个条件
    if len(conditions) > 3 and text:
        # 保留文本匹配和最多两个重要属性
        important_conditions = [c for c in conditions if 'text()' in c or 'onclick' in c or 'href' in c]
        if len(important_conditions) > 0:
            conditions = important_conditions[:3]
    
    if conditions:
        xpath = f"{xpath_base}[{' and '.join(conditions)}]"
    else:
        xpath = xpath_base
    
    print(f"构建的XPath: {xpath}")
    return xpath

def find_element_by_html(driver, html_content, container_html=None, timeout=10):
    """根据HTML内容定位元素，支持递归查找所有子元素"""
    try:
        if container_html and container_html.strip():
            print(f"\n开始查找容器元素，使用内容: {container_html}")
            tag_name, text, attrs = parse_html_content(container_html)
            container_xpath = build_xpath(tag_name, text, attrs, True)
            print(f"容器查找XPath: {container_xpath}")
            
            try:
                container = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, container_xpath))
                )
                print(f"找到容器元素: {container.tag_name}")
                
                tag_name, text, attrs = parse_html_content(html_content)
                element_xpath = build_xpath(tag_name, text, attrs)
                print(f"\n在容器中查找元素，使用XPath: {element_xpath}")
                
                elements = container.find_elements(By.XPATH, element_xpath)
                print(f"在容器中找到 {len(elements)} 个匹配元素")
                
                for i, element in enumerate(elements, 1):
                    if element.is_displayed() and element.is_enabled():
                        print(f"找到可用元素: {element.tag_name}")
                        return element
                
                print("未找到可用的元素")
                return None
                
            except TimeoutException:
                print(f"等待容器元素超时: {container_xpath}")
                return None
                
        else:
            print(f"\n直接在页面中查找元素，使用内容: {html_content}")
            tag_name, text, attrs = parse_html_content(html_content)
            element_xpath = build_xpath(tag_name, text, attrs, True)
            print(f"元素查找XPath: {element_xpath}")
            
            try:
                elements = driver.find_elements(By.XPATH, element_xpath)
                print(f"在页面中找到 {len(elements)} 个匹配元素")
                
                if not elements and text:
                    # 如果使用精确文本匹配没找到，尝试使用更宽松的文本匹配
                    print("尝试使用更宽松的文本匹配方式...")
                    loose_xpath = f"//{tag_name or '*'}[contains(text(),'{text}')]" 
                    elements = driver.find_elements(By.XPATH, loose_xpath)
                    print(f"宽松匹配找到 {len(elements)} 个匹配元素")
                
                for i, element in enumerate(elements, 1):
                    if element.is_displayed() and element.is_enabled():
                        print(f"找到可用元素: {element.tag_name}, 文本: {element.text}")
                        return element
                
                print("未找到可用的元素")
                return None
                
            except Exception as e:
                print(f"查找元素时出错: {str(e)}")
                return None
                
    except Exception as e:
        print(f"查找元素时出错: {str(e)}")
        return None

def find_element_by_text_and_url(driver, text, url_part):
    """直接使用文本内容和URL部分查找元素，这是一种更简单但可能更可靠的方法"""
    try:
        # 尝试多种XPath策略
        xpaths = [
            f"//a[contains(text(),'{text}') and contains(@onclick,'{url_part}')]",  # 文本和onclick都匹配
            f"//a[text()='{text}' and contains(@onclick,'{url_part}')]",  # 精确文本和onclick部分匹配
            f"//a[contains(text(),'{text}')]",  # 只匹配文本
            f"//a[contains(@onclick,'{url_part}')]",  # 只匹配onclick部分
            f"//p/a[contains(text(),'{text}')]",  # 考虑p标签下的a标签
            f"//p//a[contains(text(),'{text}')]",  # 考虑p标签下的任何层级的a标签
            f"//div//a[contains(text(),'{text}')]",  # 考虑div标签下的任何层级的a标签
            f"//a",  # 找出所有链接，然后在代码中筛选
        ]
        
        for i, xpath in enumerate(xpaths):
            print(f"尝试简化XPath {i+1}: {xpath}")
            elements = driver.find_elements(By.XPATH, xpath)
            print(f"找到 {len(elements)} 个匹配元素")
            
            # 如果是最后一个XPath（找所有链接），则需要手动筛选
            if i == len(xpaths) - 1 and elements:
                print("尝试手动筛选所有链接...")
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element_text = element.text.strip()
                        element_onclick = element.get_attribute('onclick') or ''
                        print(f"检查链接: 文本='{element_text}', onclick='{element_onclick}'")
                        
                        # 检查文本或onclick是否包含关键词
                        if (text.lower() in element_text.lower() or 
                            url_part.lower() in element_onclick.lower()):
                            print(f"找到匹配元素: {element.tag_name}, 文本: {element_text}")
                            return element
            else:
                # 常规XPath匹配
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        print(f"简化方法找到可用元素: {element.tag_name}, 文本: {element.text}")
                        return element
        
        # 尝试直接从tmp_web_code.txt中提取元素
        try:
            print("尝试从tmp_web_code.txt中查找元素...")
            with open('tmp_web_code.txt', 'r', encoding='utf-8') as f:
                web_code = f.read()
                
            # 查找包含文本和URL部分的a标签
            pattern = f'<a[^>]*onclick="[^"]*{url_part}[^"]*"[^>]*>{text}</a>'
            matches = re.findall(pattern, web_code, re.IGNORECASE)
            if matches:
                print(f"在tmp_web_code.txt中找到匹配: {matches[0]}")
                # 使用更精确的XPath
                precise_xpath = f"//a[contains(text(),'{text}') and contains(@onclick,'{url_part}')]" 
                elements = driver.find_elements(By.XPATH, precise_xpath)
                if elements and elements[0].is_displayed() and elements[0].is_enabled():
                    return elements[0]
        except Exception as e:
            print(f"从tmp_web_code.txt查找出错: {str(e)}")
        
        return None
    except Exception as e:
        print(f"简化查找出错: {str(e)}")
        return None