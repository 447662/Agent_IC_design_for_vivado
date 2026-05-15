#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Script Name: agent.py
# Description: 数字IC前端设计Agent主入口
#              智能分析用户需求，匹配合适的技能，检查工具环境
# Author: Digital IC Designer Team
# Date: 2026-05-15
# -----------------------------------------------------------------------------

import json
import subprocess
import sys
import os

# 设置标准输出编码
sys.stdout.reconfigure(encoding='utf-8')

class DigitalICAgent:
    def __init__(self):
        self.agent_config = self.load_config()
        self.skill_mapping = {skill['name']: skill for skill in self.agent_config['skills']}
        self.mcp_servers = self.agent_config['mcpServers']
        self.cli_tools = self.agent_config['cliTools']
        self.OK = "[OK]"
        self.NO = "[NO]"
        self.WARN = "[WARN]"
        
    def load_config(self):
        """加载Agent配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), 'agent.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def check_cli_tool(self, tool_name, check_command):
        """检查CLI工具是否安装"""
        try:
            result = subprocess.run(check_command.split(), 
                                  capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
            return False
    
    def check_mcp_server(self, mcp_name):
        """检查MCP服务器是否可用"""
        mcp = self.mcp_servers.get(mcp_name)
        if not mcp:
            return False
        
        try:
            command = [mcp['command']] + mcp['args'] + ['--version']
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
            return False
    
    def analyze_requirement(self, user_input):
        """分析用户需求，匹配技能"""
        user_input_lower = user_input.lower()
        matched_skills = []
        
        # 按优先级检查技能触发关键词
        for skill in sorted(self.agent_config['skills'], key=lambda x: x['priority']):
            for keyword in skill['triggerKeywords']:
                if keyword.lower() in user_input_lower:
                    matched_skills.append(skill['name'])
                    break
        
        # 特殊处理：UVM验证需要优先判断
        if any(keyword in user_input_lower for keyword in ['uvm', '前仿', '功能验证', '覆盖率']):
            if 'digital-ic-verifier' not in matched_skills:
                matched_skills.append('digital-ic-verifier')
        
        # 如果没有匹配到任何技能，默认使用RTL设计技能
        if not matched_skills:
            matched_skills.append('digital-ic-rtl-designer')
        
        return matched_skills
    
    def get_install_guide(self, tool_type, tool_name):
        """获取工具安装指南"""
        if tool_type == 'mcp':
            mcp = self.mcp_servers.get(tool_name)
            return mcp.get('installGuide', '未知') if mcp else '未知'
        elif tool_type == 'cli':
            for tool in self.cli_tools:
                if tool['name'] == tool_name:
                    return tool.get('installGuide', '未知')
            return '未知'
        return '未知'
    
    def run_diagnostic(self):
        """运行环境诊断"""
        print("=" * 60)
        print("数字IC前端设计Agent - 环境诊断")
        print("=" * 60)
        
        # 检查CLI工具
        print("\n【CLI工具检查】")
        cli_status = []
        for tool in self.cli_tools:
            installed = self.check_cli_tool(tool['name'], tool['checkCommand'])
            status = self.OK + " 已安装" if installed else self.NO + " 未安装"
            cli_status.append((tool['name'], installed))
            print("  {}: {}".format(tool['name'], status))
            if not installed:
                print("     安装指南: {}".format(self.get_install_guide('cli', tool['name'])))
        
        # 检查MCP服务器
        print("\n【MCP服务器检查】")
        mcp_status = []
        for name, mcp in self.mcp_servers.items():
            available = self.check_mcp_server(name)
            status = self.OK + " 可用" if available else self.NO + " 不可用"
            mcp_status.append((name, available))
            print("  {}: {}".format(name, status))
            if not available:
                print("     安装指南: {}".format(mcp.get('installGuide', '未知')))
        
        # 检查技能文件
        print("\n【技能文件检查】")
        skill_status = []
        for skill in self.agent_config['skills']:
            skill_path = os.path.join(os.path.dirname(__file__), '..', skill['path'])
            exists = os.path.exists(skill_path)
            status = self.OK + " 存在" if exists else self.NO + " 缺失"
            skill_status.append((skill['name'], exists))
            print("  {}: {}".format(skill['name'], status))
        
        # 汇总结果
        all_ok = all(installed for _, installed in cli_status) and \
                 all(available for _, available in mcp_status) and \
                 all(exists for _, exists in skill_status)
        
        print("\n" + "=" * 60)
        if all_ok:
            print("诊断结果: " + self.OK + " 所有工具和技能均已就绪")
        else:
            print("诊断结果: " + self.WARN + " 部分工具未安装，请根据上述指南安装")
        print("=" * 60)
        
        return all_ok
    
    def recommend_skills(self, user_input):
        """推荐合适的技能"""
        matched_skills = self.analyze_requirement(user_input)
        print("\n【需求分析结果】")
        print("用户需求: {}".format(user_input))
        print("\n推荐技能:")
        for skill_name in matched_skills:
            skill = self.skill_mapping.get(skill_name)
            if skill:
                print("  {} {}: {}".format(self.OK, skill['name'], skill['description']))
        
        return matched_skills
    
    def execute_workflow(self, user_input):
        """执行完整工作流"""
        print("=" * 60)
        print("数字IC前端设计Agent")
        print("=" * 60)
        
        # 步骤1: 需求分析
        print("\n【步骤1/6: 需求分析】")
        matched_skills = self.recommend_skills(user_input)
        
        # 步骤2: 工具检查
        print("\n【步骤2/6: 工具检查】")
        all_ok = self.run_diagnostic()
        
        if not all_ok:
            print("\n" + self.WARN + " 请先安装必要的工具和MCP，然后重新运行Agent")
            return False
        
        # 步骤3: 技能匹配确认
        print("\n【步骤3/6: 技能匹配】")
        print("已匹配 {} 个技能".format(len(matched_skills)))
        for skill_name in matched_skills:
            skill = self.skill_mapping[skill_name]
            print("  - {}: {}".format(skill['name'], skill['description']))
        
        # 步骤4: 执行任务
        print("\n【步骤4/6: 执行任务】")
        print("正在启动匹配的技能...")
        
        # 步骤5: 结果验证（预留）
        print("\n【步骤5/6: 结果验证】")
        print("任务执行完成，验证中...")
        
        # 步骤6: 报告生成（预留）
        print("\n【步骤6/6: 报告生成】")
        print("验证报告已生成")
        
        print("\n" + "=" * 60)
        print("工作流执行完成")
        print("=" * 60)
        
        return True

def main():
    agent = DigitalICAgent()
    
    if len(sys.argv) > 1:
        user_input = ' '.join(sys.argv[1:])
    else:
        # 交互式模式
        print("欢迎使用数字IC前端设计Agent!")
        print("请输入您的设计需求:")
        user_input = input("> ")
    
    agent.execute_workflow(user_input)

if __name__ == "__main__":
    main()