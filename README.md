# Stable Hire · MySQL-only 双边稳定招聘匹配平台


## 1. 项目核心逻辑

```text
学生填写 GPA、实习经历、技能证书、项目经历、个性描述和软技能经历。
后端 server_mysql.py 通过规则化评分函数自动生成五维能力分数。
系统再用这些分数计算双边效用矩阵并运行 Gale-Shapley 稳定匹配。
```

完整流程：

```text
学生原始文字材料 / 企业岗位信息
        ↓
后端规则化评分与标准化
        ↓
MySQL 保存结构化数据
        ↓
计算 student → company 和 company → student 双向效用
        ↓
生成双方偏好排序
        ↓
运行 Student-proposing Gale-Shapley
        ↓
输出最终匹配、阻塞对检查、算法过程和审计数据
```

## 2. 文件结构

```text
index.html              首页
student.html            学生端
company.html            企业端
admin.html              后台端
styles.css              全站样式
app.js                  前端动态渲染和交互逻辑
server_mysql.py         MySQL-only 后端服务和算法逻辑
mysql_schema.sql        MySQL 建表 SQL
mysql_seed.sql          MySQL 初始数据
assets/market-dashboard.png 首页图片资源
README.md
```

## 3. MySQL 表逻辑

### 输入数据表

- `workers`：学生 / AI Worker 的系统计算五维能力分数。
- `worker_profiles`：学生输入的原始文字材料。
- `worker_preferences`：学生评价企业时的偏好权重。
- `employers`：企业 / AI Employer 的岗位属性。
- `employer_profiles`：企业岗位文字描述。
- `employer_preferences`：企业评价学生时的偏好权重。

### 计算结果表

- `utility_scores`：双边效用矩阵。
- `matching_results`：Gale-Shapley 最终匹配结果。
- `algorithm_rounds`：每轮申请、暂时接受和拒绝过程。
- `audit_records`：审计概率、保证金和惩罚数据。

## 4. 学生文字如何转数字

学生输入会进入 `worker_profiles`：

```text
education_text      GPA、专业、课程
internship_text     实习和项目经历
skills_text         技能、证书、工具
personality_text    个性特质描述
soft_text           沟通、协作、领导、表达经历
preference_text     求职偏好描述
```

后端会自动生成并写入 `workers`：

```text
capability_signal   学历与成绩信号，范围 0-4
skills              技能/证书评分，范围 0-5
internship_history  实习/项目评分，范围 0-5
personality         个性特质评分，范围 0-1
soft_skills         软技能评分，范围 0-1
```

例如：

```text
skills_text = "Python, SQL, Tableau, CET-6，有数据分析项目"
        ↓
server_mysql.py 识别 Python、SQL、Tableau、CET-6、项目等关键词
        ↓
skills = 系统计算后的技能分
```

这个版本是 rule-based scoring，不是假装已经接入真正的大模型 NLP。后续如果接入 AI API，可以替换 `infer_worker_scores()` 相关函数。

## 5. 数据规模

初始数据包含：

```text
20 个普通学生
2 个 AI Worker
20 个普通企业 / 岗位
2 个 AI Employer
共 22 × 22 双边效用矩阵
最终输出 22 组一对一稳定匹配
blocking pairs = 0
```

当前算法是 one-to-one matching。也就是说：一个学生最多匹配一个企业，一个企业最多匹配一个学生。如果要改成真实招聘中“一家公司多个岗位名额”，需要把 Gale-Shapley 改成 many-to-one matching，并给企业增加 `capacity` 字段。

## 6. 启动方法

### 第一步：导入建表 SQL

```bash
mysql -u root -p < mysql_schema.sql
```

### 第二步：导入初始数据

```bash
mysql -u root -p stable_hire < mysql_seed.sql
```

### 第三步：启动后端

默认连接参数：

```text
host: 127.0.0.1
port: 3306
user: stable_user
password: stable_pass
database: stable_hire
```

启动：

```bash
python3 server_mysql.py
```

如果你使用 root 用户：

```bash
MYSQL_USER=root MYSQL_PASSWORD=你的密码 python3 server_mysql.py
```

### 第四步：打开页面

```text
http://127.0.0.1:8000/index.html
http://127.0.0.1:8000/student.html
http://127.0.0.1:8000/company.html
http://127.0.0.1:8000/admin.html
```

## 7. API

```text
GET  /api/state
POST /api/state
POST /api/reset
```

- `GET /api/state`：读取 MySQL，自动评分，重新计算匹配并返回前端。
- `POST /api/state`：保存学生/企业修改后的 state，后端自动评分并重新计算。
- `POST /api/reset`：重新导入 `mysql_seed.sql`，恢复示例数据。
