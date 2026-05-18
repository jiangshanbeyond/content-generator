# GitHub Token (通过环境变量 GITHUB_TOKEN 传入，不提交到仓库)
import os
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "jiangshanbeyond/content-generator"