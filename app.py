from flask import Flask, request, jsonify, render_template, send_from_directory
from openai import OpenAI
import os
import io
import sys
import matplotlib
matplotlib.use('Agg')  # 使用 Agg 后端
import matplotlib.pyplot as plt
import time
import random
import string
import re

app = Flask(__name__)

# 初始化 OpenAI 客户端
client = OpenAI(base_url="http://localhost:5001/v1/", api_key="sk-xxxx")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.form.get('user_input')
    messages = request.form.getlist('messages')
    file = request.files.get('file')
    
    # 处理文件上传
    if file:
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)
    else:
        file_path = None

    # 添加用户消息到消息列表
    messages.append({"role": "user", "content": user_input})
    
    response = None
    if user_input != "":
        # 添加用户消息到消息列表
        messages.append({"role": "user", "content": user_input})
        
        # 调用 OpenAI API 生成响应
        completion = client.chat.completions.create(
            temperature=0,
            model="local",
            messages=messages
        )
        # 获取模型的响应
        response = completion.choices[0].message.content
    
    # 如果有文件上传，包含文件路径信息
    if file_path:
        if response == None:
            response = f"文件已保存到: {file_path}"
        else:
            response += f"\n文件已保存到: {file_path}"
    
    return jsonify({"response": response, "messages": messages})

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    code = data.get('code')
    
    try:
        # 打印接收到的代码
        print("Received code:", code)
        
        # 切换到 uploads 目录并执行代码
        os.chdir('uploads')
        exec_globals = {}
        exec_locals = {}
        
        # 捕获标准输出
        stdout = io.StringIO()
        sys.stdout = stdout
        
        # 在执行代码之前导入所有在代码中出现的库
        import_statements = re.findall(r'^\s*import\s+(\S+)(?:\s+as\s+(\S+))?', code, re.MULTILINE)
        from_import_statements = re.findall(r'^\s*from\s+(\S+)\s+import\s+(\S+)(?:\s+as\s+(\S+))?', code, re.MULTILINE)
        
        for module, alias in import_statements:
            if alias:
                exec(f"import {module} as {alias}", exec_globals, exec_locals)
                exec_globals[alias] = exec_locals[alias]
            else:
                exec(f"import {module}", exec_globals, exec_locals)
                exec_globals[module] = exec_locals[module]
        
        for module, submodule, alias in from_import_statements:
            if alias:
                exec(f"from {module} import {submodule} as {alias}", exec_globals, exec_locals)
                exec_globals[alias] = exec_locals[alias]
            else:
                exec(f"from {module} import {submodule}", exec_globals, exec_locals)
                exec_globals[submodule] = exec_locals[submodule]

        # 记录现有的文件列表
        existing_files = set(os.listdir('.'))
        
        exec(code, exec_globals, exec_locals)
        
        # 恢复标准输出
        sys.stdout = sys.__stdout__
        
        # 获取执行结果
        result = stdout.getvalue()
        print("Result:", result)

        # 生成图像
        if 'plt.show()' in code:
            plt.gcf().canvas.draw()
            # 生成唯一的文件名
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            filename = f'output_{timestamp}_{random_str}.png'
            plt.savefig(filename)
            plt.close()
            if os.path.exists(filename):
                result += f"\n<img src='/uploads/{filename}' />"

        # 检查是否生成了新文件
        new_files = set(os.listdir('.')) - existing_files
        for file in new_files:
            if os.path.isfile(file):
                result += f"\n<a href='/uploads/{file}' download class='download-link'>{file}</a>"

        os.chdir('..')
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)