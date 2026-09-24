# 订单详情、物流跟踪与运费估算（Python + Vue）

一个小型全栈演示应用：读取本地订单文件和 SKU 文件，按 SKU 匹配产品信息，计算小计、GST、运费和总价，并按追踪号调用快递 API 显示物流状态。

**需求以原始考题 PDF（`2026-06-IT-Interview-in-person.pdf`）为准**。另有一份较新的 HTML 说明（含 API 凭证和 FAQ），两者有冲突时以 PDF 为准，差异见第 9 节。

- 后端：Python 3.11 + FastAPI + httpx + Pydantic
- 前端：Vue 3 + Vite（无 UI 组件库）
- 数据：本地 JSON 文件（无数据库）
- 输出：网页（主要）、控制台表格和 JSON（补充）

---

## 1. 如何运行

### 准备
- Python 3.11+
- Node.js 18+（开发时使用 22）

### 配置密钥（`.env`）
```bash
cp .env.example .env      # 然后填写 API Key / 密码 / 账号
```
- `.env` 已被 `.gitignore` 排除，**绝不提交到 GitHub**；仓库中只有只含变量名的 `.env.example`。
- `.env` 可以放在仓库以外的安全位置，用环境变量 `ENV_FILE` 指定路径，例如 PowerShell：`$env:ENV_FILE="D:\secure\aeris.env"`。
- 访问 `http://localhost:8000/api/health` 可检查每个变量是否已读取（只显示 true/false，不显示值）。
- 不填写任何密钥应用也能完整运行：物流显示「Not configured」，运费自动使用公式估算。

### 后端
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
- API 文档 / JSON 视图：http://localhost:8000/docs
- 控制台输出：`python scripts/print_orders.py`（加 `--json` 输出 JSON，或加订单号只看一个订单）
- 测试：`pytest`（34 个测试）

### 前端
```bash
cd frontend
npm install
npm run dev
```
打开 http://localhost:5173 。Vite 将 `/api` 代理到 8000 端口，无需配置 CORS，浏览器端不接触任何快递密钥。

---

## 2. 依赖
| 部分 | 依赖 | 作用 |
|---|---|---|
| 后端 | fastapi, uvicorn | Web API |
| 后端 | pydantic, pydantic-settings | 数据校验、读取 `.env` |
| 后端 | httpx | 异步调用快递 API（带超时） |
| 测试 | pytest, respx | 单元测试、模拟 HTTP |
| 前端 | vue, vite, @vitejs/plugin-vue | 界面 |

---

## 3. 输入数据结构（`backend/data/`）

对应 PDF 要求的「读取订单文件、读取 SKU 文件」。**真实订单只要遵循同样的结构即可直接使用**；每次请求都会重新读取文件，替换后刷新页面即可。

| 文件 | 内容 |
|---|---|
| `orders.json` | 订单头：`order_no, order_date (YYYY-MM-DD), status, company, customer, phone, email, address{street, suburb, state, postcode}`，可选 `is_test, test_note` |
| `order_lines.json` | SKU 行：`sku, quantity, tracking_ref, order_no`（与 PDF 表格一致） |
| `shipments.json` | 追踪信息：`tracking_ref, tracking_no, carrier (AUSPOST / STARTRACK / TNT), logistics_company` |
| `product_*.json` | SQL 查询网站返回的**原始 JSON**，原样保存；多个文件自动合并 |
| `product_images.json` | `SKU → 图片 URL`（在线搜索得到的真实产品图），没有则使用占位图 |
| `shipping_rates.json` | 运费公式的**假设**费率表（仅在拿不到快递报价时使用） |

### 获取 SKU 数据（SQL-like 查询网站）
使用 PDF 中的地址 https://tinyurl.com/2zp5p54a （需要登录 Google 账号）。表名为 `product_list`，价格字段为 `RRP`。网站**默认只返回 10 行**（`SELECT * FROM product_list` 的结果中 `"limit": 10`，且不包含任何订单 SKU），因此需要按 SKU 过滤：
```sql
SELECT * FROM product_list WHERE SKU IN ('TBAMET10','TBAMET28','TBOPAL28','AURPUR10','HARNIG','LELCBD100','HALGEO15','MCMW10','MCBO30');
```
结果（`rowCount: 9`，全部匹配）保存为 `backend/data/product_list.json`。

---

## 4. 计算规则（按 PDF 原文）

| 项目 | 公式 |
|---|---|
| Price per unit | SKU 价格（`RRP`） |
| Line Total | SKU 价格 × 数量 |
| Subtotal | 所有 Line Total 之和 |
| GST | Subtotal × 10% |
| Total | Subtotal + GST + Shipment Fee |

- 全程使用 Python `Decimal` + `ROUND_HALF_UP`，不使用浮点数；金额以字符串（如 `"199.00"`）传给前端，前端只负责格式化（`A$1,234.50`）。
- 每个订单独立计算，不同收件人的订单不会合并。
- **注意**：PDF 同时写明「SKU price already includes GST」，而公式又在含税价格上再加 10% GST，等于 **GST 重复计算**。本项目按要求严格执行 PDF 公式，但在此说明这一点；如果改为从含税价中拆分 GST（`RRP / 1.10`），只需修改 `app/services/pricing.py` 一个文件。

手工核对（与程序输出一致）：

| 订单 | Subtotal | GST | Shipment Fee | Total |
|---|---|---|---|---|
| PO-20251130-00072 | 297 + 199 + 199 + 596 + 840 = **A$2,131.00** | A$213.10 | A$16.90（StarTrack，公式估算） | **A$2,361.00** |
| PO-20251203-00046 | 990 + 110 + 258 + 297 = **A$1,655.00** | A$165.50 | A$15.80（StarTrack，公式估算）+ A$0.00（TNT） | **A$1,836.30** |

---

## 5. 物流跟踪

- 追踪属于**包裹**而不是订单，一个订单可以有多个包裹、多个快递。结构为：订单 → 包裹（按 `tracking_ref` 分组）→ SKU 行；每个包裹单独查询物流、单独计算运费，订单运费 = 各包裹运费之和。
- 使用哪家快递由 `shipments.json` 中的 `carrier` 决定（PDF：「call the correct API based on the logistics company」）。
- **Australia Post / StarTrack**：`GET {BASE}/track?tracking_ids=...`，HTTP Basic（API Key : 密码）+ `Account-Number` 请求头；AusPost 账号 2004456017，StarTrack 账号 04456017。每次最多 10 个单号，成功结果缓存 5 分钟，超时 10 秒。
- 密钥只在后端使用。客户端从不抛出异常，所有失败都显示为明确状态，**不会编造物流结果**：

| 状态 | 含义 |
|---|---|
| `OK` | 返回了当前状态、最后更新时间和事件时间线 |
| `NO_DATA` | API 正常但该单号无数据 / 单号无效 |
| `UNAVAILABLE` | 超时、HTTP 错误、返回非 JSON 等 |
| `NOT_CONFIGURED` | `.env` 缺少必要变量（不发出请求） |
| `NOT_IMPLEMENTED` | TNT（见下文） |

### 实际测试结果（2026-09-24）
使用 `backend/scripts/probe_auspost.py` 对测试环境 `https://digitalapi.auspost.com.au/test/shipping/v1` 进行了测试：
- 两个账号对 `track`（订单单号及 4 个额外测试单号）和 `accounts/{账号}` 均返回 **HTTP 401 `API_001` "The request failed authentication"**。
- 用 curl 直接请求结果相同，并且与**不带任何凭证**的请求结果完全一样，说明问题不在客户端代码，而是测试环境不接受所提供的凭证（可能已过期或停用）。
- 为排除调用方式的问题，又测试了以下变体，**全部返回同样的 401**：

  | # | 变体 | 结果 |
  |---|---|---|
  | 1–3 | Account-Number 分别使用 AusPost 2004456017 / StarTrack 04456017 / Same Day 3004456017 | 401 |
  | 4 | 不带 Account-Number | 401 |
  | 5 | 使用 `AUTH-KEY` 请求头代替 Basic 认证 | 401 |
  | 6 | 其他接口（`GET accounts/{账号}`） | 401 |
  | 7 | 生产环境地址（去掉 `/test`） | 401 |
  | 8 | 对照组：随意编造的 Key / 密码 | 401 |

  提供的凭证与编造的凭证结果完全相同，说明网关在认证这一步就拒绝了该 API Key，与账号、快递公司（AusPost 或 StarTrack）和单号无关。

- **查阅官方文档后的结论**：
  1. 调用方式正确：官方 FAQ 给出的测试命令就是 `curl --header "Account-Number: xxx" --user "api_key" ".../test/shipping/v1/track?tracking_ids=11111"`，即 Basic 认证 + `Account-Number` 请求头，与本项目完全一致；按该命令原样执行仍返回 401。
  2. 官方对 `API_001` 的解释是「认证错误」；测试环境文档写明测试环境会像生产环境一样**校验凭证（API key 和密码）**，所以是凭证本身未通过校验。
  3. 凭证格式正常（key 为标准 36 位 UUID，密码 20 位，`.env` 中没有隐藏空格或换行）。
  4. AusPost 已推出 **Shipping and Tracking API v2**，改用 OAuth 2.0：用 `client_id` / `client_secret` 向 `https://welcome.api1.auspost.com.au/oauth/token` 申请令牌（`grant_type=client_credentials`，`audience=https://digitalapi.auspost.com.au/shipping/v2`），再用 `Authorization: Bearer <token>` 调用 API。旧版文档站的发布说明停在 2018 年。把考题提供的 key / 密码当作 `client_id` / `client_secret` 去申请令牌，返回 `access_denied / Unauthorized`，说明考题提供的是**旧版 v1 凭证**，不是 v2 凭证。
  5. **最可能的原因**：考题中的 v1 测试凭证已过期或被停用（例如随 v1 → v2 迁移失效）。无法从外部进一步区分「key 已停用」和「密码不匹配」，因为两者返回同样的 401。如果凭证是从截图或邮件手工转录的，也可能有易混淆字符（如 `1` / `l` / `I`），需要与原始来源核对。
  6. **解决办法**：向出题方确认凭证是否仍有效，或索取新的测试凭证（v1 的 API key + 密码，或 v2 的 `client_id` + `client_secret`）。如果拿到 v2 凭证，只需在 `couriers/auspost.py` 中增加「申请令牌 → Bearer 认证」一步，其余代码不变。
- 因此界面对 AusPost/StarTrack 显示「Unavailable（HTTP 401）」，运费回退到公式估算。凭证更新后无需修改代码：运行 probe 脚本，从 `accounts` 响应中选出产品 ID 填入 `AUSPOST_PRODUCT_ID` / `STARTRACK_PRODUCT_ID`，即可启用实时跟踪和快递报价。
- 实际错误格式为 `error_code / error_name / message`（部分文档为 `code / name`），客户端两种都兼容。

### TNT（未实现）
TNT 使用基于 XML 的 RTT（报价）和 Secured Weblinking（跟踪），接入方式与 AusPost 完全不同。TNT 包裹显示「Not implemented」，运费 **A$0.00**（PDF：「If you cannot finish it, just show $0.00」）。`couriers/tnt.py` 与 AusPost 客户端接口相同，以后可以直接替换。

---

## 6. 运费估算（加分项，按包裹计算）

PDF 允许「使用快递 API」或「基于重量和体积的合理公式」。本项目两者都实现：优先使用**快递官方报价**，失败时使用公式。

1. **组包**：
   - 重量 = Σ(单件重量 × 数量) + 纸箱 0.1 kg。单件重量取 `Volumetric_GrossWeight` 与 `weight` **中较大的值**：实际数据中毛重有时比净重还轻（如 HALGEO15：毛重 0.02 kg，净重 68 g），这不合理，所以取较大值。
   - 尺寸：假设所有商品装入一个纸箱，最小 22×16×7.7 cm（相当于 AusPost 小号盒）；货物总体积（`volume` 或 长×宽×高）× 1.25 超过纸箱容量时按比例放大。
2. **AusPost / StarTrack → 快递报价 API**：`POST {BASE}/prices/items`，发件邮编 2111（Ryde NSW），收件邮编取自客户地址，加上包裹尺寸和重量；使用返回的 `calculated_price`（含 GST），界面标注「Courier quote」。
3. **报价失败 → 公式估算**（界面标注「Estimate (formula)」并显示原因）：
   - 体积重 = 长×宽×高 (m³) × 250 kg/m³（AusPost/StarTrack 通用换算系数）
   - 计费重 = max(实重, 体积重, 0.5 kg)，向上取整到 0.5 kg
   - 运费 = 区域基础价 + 每公斤单价 × 计费重
   - 区域按收件州和邮编判断：同州市区 / 同州偏远 / 跨州市区 / 跨州偏远 / NT 偏远
   - **费率均为假设值**（`shipping_rates.json`），不是真实价目表，修改文件即可调整
4. **TNT → A$0.00**。

运费按 PDF 公式直接加到 Total 中（Total = Subtotal + GST + Shipment Fee），不对运费另计 GST。

---

## 7. 产品图片

按 PDF 第 6 条：先**按 SKU 名称在线搜索图片**，找不到再用占位图。
- 找到并确认为真实产品照片的：**AURPUR10**（Aura Purple Raine，来源 cannexa.com.au）。
- 其他 SKU 在 cannareviews.health 等网站上只能找到**品牌 Logo**（Tasmanian Botanics、Aura Harbour、Limited Edition Labs、Spyn），不是 SKU 图片，因此未使用；Maali Wind、BOB 30 未找到。
- 这些 SKU 显示生成的药瓶占位图，标注「Product 1」「Product 2」……
- 所有图片 URL 均用 curl 验证过可以访问；如果图片以后失效，前端自动回退到占位图。
- 在 `product_images.json` 中添加 `SKU → URL` 即可补充图片，无需改代码。

---

## 8. 数据异常处理与测试订单

每一行都有状态，异常行**显示但不计入金额**，并在订单顶部显示警告：

| 状态 | 情况 |
|---|---|
| `SKU_NOT_FOUND` | SKU 数据中找不到（匹配时忽略大小写和首尾空格） |
| `INVALID_QTY` | 数量不是 ≥ 1 的整数（0、负数、小数、文字等；`"3"` 这样的数字字符串可以接受） |
| `BAD_PRODUCT_DATA` | 产品价格无法解析 |

另外还检查跨文件问题：SKU 行引用了不存在的订单号（相似订单号会提示「did you mean」）、`tracking_ref` 在 `shipments.json` 中不存在等。

**测试订单**：交付给客户的网页只显示两个真实订单，`backend/data/` 中不包含任何测试数据。异常情况改由 `backend/tests/` 中的自动化测试覆盖（使用临时数据目录，不影响交付数据），包括：不存在的 SKU、数量 0 / -1 / 1.5 / 文字、价格无法解析、订单号笔误、未知追踪编号、多包裹多快递、快递 API 超时 / 401 / 返回非 JSON、报价失败回退公式、各运费区域等。数据格式仍支持可选字段 `is_test`（界面会标注 TEST DATA），便于以后在开发环境中加入演示数据。

---

## 9. 发现的难点及解决方法

| 难点 | 解决方法 |
|---|---|
| PDF 中订单 2 的表头订单号为 `PO-20251202-00046`，而 SKU 表中写的是 `PO-20251203-00046` | 已确认正确订单号为 **`PO-20251203-00046`**（SKU 表的 4 行及订单日期 03/12/25 都与之一致），表头的 `1202` 是笔误。程序本身**不会自动合并**订单号不一致的数据：若 SKU 行引用了不存在的订单号，会作为数据警告列出并提示相似订单号（「did you mean …?」），对应订单显示「没有 SKU 行」。这一检查最初正是用来发现这个笔误的，并有单元测试覆盖 |
| PDF 公式在含税价格上再加 GST | 按 PDF 执行，并在第 4 节说明（新版 HTML 说明改为 `RRP / 1.10`） |
| 查询网站默认只返回 10 行；HTML 说明中的查询网址与 PDF 不同 | 使用 PDF 的网址，并用 `WHERE SKU IN (...)` 取得全部 9 个 SKU |
| 查询结果的所有字段都是带单位的字符串（`"76.0mm"`、`"68.0g"`、`"450528.0mm³"`、`"0.02kg"`），且含换行符 | 用正则解析并统一单位；无法解析的值记为空并给出警告，程序不会崩溃 |
| 毛重小于净重（数据矛盾） | 取两者较大值作为运费重量 |
| 一个订单有多个包裹、不同快递 | 以包裹为单位查询物流和计算运费 |
| 浮点数误差 | `Decimal` + 金额以字符串传输 |
| 在线图片大多是品牌 Logo 而非产品图 | 只使用确认是产品照片的图片，其他用占位图 |
| 测试环境凭证返回 401 | 所有失败都显示为明确状态，运费回退到公式，并在第 5 节记录测试过程 |
| 密钥安全（考题文件本身含有凭证） | `.env` + `.gitignore`（考题 PDF 和 HTML 也被排除）；前端无密钥；`/api/health` 只显示是否已配置 |
| Windows 控制台 GBK 编码无法输出 `mm³` | 所有文件以 UTF-8 读取，控制台脚本强制 UTF-8 输出 |

---

## 10. 项目结构
```
backend/
  app/main.py              API 路由（/api/orders, /api/orders/{no}, /api/health）
  app/config.py            读取 .env（支持 ENV_FILE）
  app/models.py            输入 / 输出数据模型
  app/services/loader.py   读取 JSON 数据并检查一致性
  app/services/products.py 解析 SKU 数据（单位、文本清理、运费重量）
  app/services/pricing.py  Line Total / Subtotal / GST / Total
  app/services/orders.py   组装订单：匹配、校验、分包裹、物流、运费、合计
  app/services/shipping.py 组包、快递报价、公式回退
  app/couriers/auspost.py  Australia Post / StarTrack 客户端
  app/couriers/tnt.py      TNT 占位实现
  scripts/print_orders.py  控制台 / JSON 输出
  scripts/probe_auspost.py 测试环境连通性检测
  tests/                   pytest
frontend/src/
  App.vue, components/     订单列表、订单详情、SKU 行、物流卡片、合计
```
