# This version update the PDF reader to use PyMuPDF and add OCR functionality.
# Add a GUI using Tkinter to input the API key and folder path and command for deepseek.
import os
import webbrowser
import time
import keyboard  # 需要安装keyboard模块：pip install keyboard
import fitz  # PyMuPDF, 需要安装：pip install PyMuPDF
import requests  # 需要安装：pip install requests
import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox
from PIL import Image
import pytesseract  # 需要安装 pytesseract 和 Pillow: pip install pytesseract Pillow
import io

# 提取 PDF 文本内容的函数
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text_per_page = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text_per_page.append(page.get_text())  # 使用 get_text() 方法提取每页文本
    return text_per_page

# 提取 PDF 中固定页数的图片并应用 OCR 进行文字提取
def extract_text_from_images(pdf_path, page_numbers):
    doc = fitz.open(pdf_path)
    text_from_images_per_page = {}

    # 获取 PDF 页数
    num_pages = len(doc)

    for page_num in page_numbers:
        if page_num >= num_pages:
            print(f"警告：页码 {page_num} 超出范围，文档只有 {num_pages} 页。")
            continue  # 跳过这个页码

        page = doc.load_page(page_num)
        img_list = page.get_images(full=True)
        text_from_images = ""
        for img_index, img in enumerate(img_list):
            xref = img[0]  # 图像的 xref
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            # 使用 Pillow 打开图像并应用 OCR
            image = Image.open(io.BytesIO(image_bytes))
            text_from_images += pytesseract.image_to_string(image)  # 进行 OCR 处理

        text_from_images_per_page[page_num] = text_from_images  # 保存该页的图像文本

    return text_from_images_per_page

# 合并图像文本和 PDF 文本
def merge_text_and_images(pdf_text, image_text):
    merged_text = ""
    for i in range(len(pdf_text)):
        page_text = pdf_text[i]
        if i in image_text:
            page_text += "\n\n[Image Text]\n" + image_text[i]  # 将图片文本合并到相应的页面
        merged_text += page_text + "\n\n"  # 合并每一页的文本
    return merged_text

# 调用 DeepSeek API 进行总结
def summarize_pdf(text, deepseek_api_key, custom_instruction):
    """
    使用 DeepSeek API 对提取的 PDF 文本进行总结。

    :param text: 提取的 PDF 文本
    :param deepseek_api_key: DeepSeek API 的密钥
    :return: 总结后的文本
    """
    headers = {
        'Authorization': f'Bearer {deepseek_api_key}',
        'Content-Type': 'application/json'
    }

    data = {
        "model": "deepseek-chat",  # 使用 DeepSeek 的 chat 模型
        "messages": [
            {"role": "user", "content": f"{custom_instruction}: {text}"}
        ]
    }

    response = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)

    if response.status_code == 200:
        response_data = response.json()
        summary = response_data['choices'][0]['message']['content']

        if summary.strip() == "":
            return "没有返回总结内容"
        else:
            return summary
    else:
        return f"Error: {response.status_code}, {response.text}"

# 在 Tkinter 窗口中显示总结内容
def show_summary_in_window(summary, pdf_file):
    # 创建新的 Tkinter 窗口来显示总结
    summary_window = tk.Tk()
    summary_window.title(f"总结 - {pdf_file}")
    summary_window.geometry("800x600")  # 设置窗口的大小

    text_box_frame = tk.Frame(summary_window)
    text_box_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # 添加垂直滚动条
    scroll_bar = tk.Scrollbar(text_box_frame)
    scroll_bar.pack(side=tk.RIGHT, fill=tk.Y)

    # 创建文本框，指定字体、字号和其他参数
    text_box = scrolledtext.ScrolledText(text_box_frame, wrap=tk.WORD, font=("Arial", 12), height=20, width=80, yscrollcommand=scroll_bar.set)

    # 配置标题加粗并转为大写
    text_box.tag_configure("title", font=("Arial", 14, "bold"), foreground="blue")
    text_box.insert(tk.END, "SUMMARY\n", "title")  # 标题，设置为大写加粗
    text_box.insert(tk.END, summary)  # 插入总结内容
    text_box.config(state=tk.DISABLED)  # 设置文本框为只读
    text_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # 配置滚动条与文本框的连接
    scroll_bar.config(command=text_box.yview)

    # 添加保存按钮
    save_button = tk.Button(summary_window, text="保存总结", command=lambda: save_summary_to_file(summary))
    save_button.pack(padx=10, pady=10)

    summary_window.mainloop()

# 保存总结到文件
def save_summary_to_file(summary):
    with open("summary.txt", "w", encoding="utf-8") as file:
        file.write(summary)
    messagebox.showinfo("保存成功", "总结已保存到 summary.txt 文件中!")

# 运行任务函数
def run_task(event=None):
    deepseek_api_key = api_key_entry.get()
    folder_path = folder_path_entry.get()
    custom_instruction = custom_instruction_entry.get()

    # 检查输入是否有效
    if not deepseek_api_key or not folder_path:
        messagebox.showerror("错误", "请输入有效的 API 密钥和文件夹路径！")
        return

    # 检查文件夹路径是否存在
    if not os.path.isdir(folder_path):
        messagebox.showerror("错误", f"文件夹路径 '{folder_path}' 不存在！")
        return

    # 获取文件夹中的 PDF 文件
    pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
    if not pdf_files:
        messagebox.showerror("错误", f"文件夹中没有 PDF 文件！")
        return

    # 关闭当前窗口
    root.destroy()

    # 开始处理 PDF 文件
    for pdf_file in pdf_files:
        pdf_path = os.path.join(folder_path, pdf_file)

        print(f"正在处理 {pdf_file}...")

        webbrowser.open(f'file://{pdf_path}')

        # 提取 PDF 内容中的文字
        pdf_text = extract_text_from_pdf(pdf_path)

        # 提取图像中的文字
        image_text = extract_text_from_images(pdf_path, [0, 1])  # 处理前两页

        # 合并 PDF 和图像文本
        combined_text = merge_text_and_images(pdf_text, image_text)

        # 调用 DeepSeek API 进行总结
        summary = summarize_pdf(combined_text, deepseek_api_key, custom_instruction)

        print(f"总结：{summary}")

        # 弹出窗口显示总结
        show_summary_in_window(summary, pdf_file)

        # 等待一段时间，防止过快触发 API 请求
        time.sleep(1)

    messagebox.showinfo("完成", "任务已完成！")

# 创建主窗口
root = tk.Tk()
root.title("PDF 文档总结工具")

# 设置窗口大小
root.geometry("400x250")

# 创建标签和输入框
api_key_label = tk.Label(root, text="DeepSeek API 密钥:")
api_key_label.pack(pady=10)
api_key_entry = tk.Entry(root, width=50)
api_key_entry.pack(pady=5)

folder_path_label = tk.Label(root, text="PDF 文件夹路径:")
folder_path_label.pack(pady=10)
folder_path_entry = tk.Entry(root, width=50)
folder_path_entry.pack(pady=5)

custom_instruction_label = tk.Label(root, text="自定义指令:")
custom_instruction_label.pack(pady=10)
custom_instruction_entry = tk.Entry(root, width=50)
custom_instruction_entry.pack(pady=5)


# 绑定回车键来启动任务
root.bind('<Return>', run_task)

# 运行按钮
run_button = tk.Button(root, text="开始运行", command=run_task)
run_button.pack(pady=20)

# 启动 Tkinter 事件循环
root.mainloop()
