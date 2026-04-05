<div align="center">

![QuantAgent Banner](assets/banner.png)
<h2>QuantAgent: ระบบตัวแทน LLM สำหรับการวิเคราะห์การซื้อขายความถี่สูงที่ขับเคลื่อนด้วยราคา</h2>

</div>

<div align="center">

<div style="position: relative; text-align: center; margin: 20px 0;">
  <div style="position: absolute; top: -10px; right: 20%; font-size: 1.2em;"></div>
  <p>
    <a href="https://machineily.github.io/">Fei Xiong</a><sup>1,2 ★</sup>&nbsp;
    <a href="https://wyattz23.github.io">Xiang Zhang</a><sup>3 ★</sup>&nbsp;
    <a href="https://scholar.google.com/citations?user=hFhhrmgAAAAJ&hl=en">Aosong Feng</a><sup>4</sup>&nbsp;
    <a href="https://intersun.github.io/">Siqi Sun</a><sup>5</sup>&nbsp;
    <a href="https://chenyuyou.me/">Chenyu You</a><sup>1</sup>
  </p>
  
  <p>
    <sup>1</sup> Stony Brook University &nbsp;&nbsp; 
    <sup>2</sup> Carnegie Mellon University &nbsp;&nbsp;
    <sup>3</sup> University of British Columbia &nbsp;&nbsp; <br>
    <sup>4</sup> Yale University &nbsp;&nbsp; 
    <sup>5</sup> Fudan University &nbsp;&nbsp; 
    ★ ผู้มีส่วนร่วมเท่าเทียมกัน <br>
  </p>
</div>

<div align="center" style="margin: 20px 0;">
  <a href="README.md">English</a> | <a href="README_CN.md">中文</a> | <a href="README_TH.md">ภาษาไทย</a>
</div>

<br>
<p align="center">
  <a href="https://arxiv.org/abs/2509.09995">
    <img src="https://img.shields.io/badge/💡%20ArXiv-2509.09995-B31B1B?style=flat-square" alt="Paper">
  </a>
  <a href="https://Y-Research-SBU.github.io/QuantAgent">
    <img src="https://img.shields.io/badge/Project-Website-blue?style=flat-square&logo=googlechrome" alt="Project Website">
  </a>
  <a href="https://github.com/Y-Research-SBU/QuantAgent/blob/main/assets/wechat_0203.jpg">
    <img src="https://img.shields.io/badge/WeChat-Group-green?style=flat-square&logo=wechat" alt="WeChat Group">
  </a>
  <a href="https://discord.gg/t9nQ6VXQ">
    <img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat-square&logo=discord" alt="Discord Community">
  </a>
</p>

</div>


ระบบประเมินการซื้อขายแบบ Multi-Agent ที่ซับซ้อน ครอบคลุมทั้งการวิเคราะห์ทางเทคนิค (Technical Indicators) การจดจำรูปแบบ (Pattern Recognition) และการวิเคราะห์แนวโน้ม (Trend Analysis) โดยใช้ LangChain และ LangGraph ระบบนี้มีทั้ง Web Interface และการดึงข้อมูลผ่านโปรแกรมเพื่อการวิเคราะห์ตลาดอย่างครอบคลุม


<div align="center">

🚀 [ฟีเจอร์](#-ฟีเจอร์) | ⚡ [การติดตั้ง](#-การติดตั้ง) | 🎬 [วิธีใช้งาน](#-วิธีใช้งาน) | 🔧 [รายละเอียดการทำงาน](#-รายละเอียดการทำงาน) | 🤝 [การมีส่วนร่วม](#-การมีส่วนร่วม) | 📄 [ไลเซนส์](#-ไลเซนส์)

</div>

## 🚀 ฟีเจอร์

  ### Indicator Agent (ตัวแทนวิเคราะห์อินดิเคเตอร์)
  
  • คำนวณอินดิเคเตอร์เชิงเทคนิค 5 ชนิด เช่น RSI เพื่อประเมินความผันผวน, MACD เพื่อวัดแนวโน้มพฤติกรรม Convergence-Divergence, และ Stochastic Oscillator สำหรับเปรียบเทียบราคาปัจจุบันกับช่วงที่ผ่านมา โดยคำนวณบนข้อมูล K-line เพื่อเปลี่ยนข้อมูล OHLC ดิบให้กลายเป็นสัญญาณพร้อมใช้งาน
  
  ![indicator agent](assets/indicator.png)
  
 ### Pattern Agent (ตัวแทนอ่านรูปแบบ)
  
  • เมื่อมีการเรียกใช้ Pattern Agent จะทำการวาดกราฟราคาก่อนเพื่อจำแนกจุดสูงสุดและต่ำสุดหลักๆ  รวมถึงการเคลื่อนที่ขึ้นลงแบบกว้างๆ แล้วเปรียบเทียบรูปแบบเหล่านั้นกับฐานข้อมูล ก่อนประมวลผลสรุปรูปแบบกราฟออกมาเป็นข้อความสั้นๆ ที่อ่านเข้าใจง่าย

  ![pattern agent](assets/pattern.png)
  
  ### Trend Agent (ตัวแทนวิเคราะห์แนวโน้ม)
  
  • ทำหน้าที่วาดกราฟด้วยเส้น Channel (ทั้งกรอบบนและล่าง) ลากผ่านจุด High-Low ล่าสุด เพื่ออธิบายทิศทางของตลาด, วัดระดับความชัน, มองหาช่วงไซด์เวย์ (Consolidation Zones) และสรุปแนวโน้มตลาดปัจจุบันแบบมืออาชีพ
  
  ![trend agent](assets/trend.png)

  ### Decision Agent (ตัวแทนตัดสินใจ)
  
  • สังเคราะห์ข้อมูลจากการทำงานของ Indicator, Pattern, Trend, และ Risk Agent เข้าด้วยกัน (เช่น ข้อมูลความผันผวน, กราฟ, ทิศทางตลาด และความเสี่ยงต่อผลตอบแทน) เพื่อตัดสินใจสั่ง "LONG" หรือ "SHORT" พร้อมแนะนำจุดเข้าซื้อ (Entry) จุดเทขาย (Exit) และราคาหยุดขาดทุน (Stop-loss) ท้ายที่สุดมาพร้อมเหตุผลเชิงผลลัพธ์ที่ชัดเจน

  ![decision agent](assets/decision.png)

### Web Interface (หน้าเว็บ)
ระบบแอปพลิเคชัน Flask ที่ทันสมัยและตอบสนองได้ดีพร้อมฟีเจอร์:
  - ข้อมูลตลาดแบบเรียลไทม์จากแหล่งข้อมูลหลายแห่ง (Yahoo Finance, MetaTrader 5, Binance, Bitkub)
  - รองรับการเลือก Asset แบบอินเตอร์แอคทีฟ (หุ้น, คริปโต, ฟอเร็กซ์, สินค้าโภคภัณฑ์)
  - สามารถสลับการวิเคราะห์ตามตัวกรองได้เอง (ระหว่างระบุช่วงวันที่ หรือขอบเขตเวลาจำนวน Bars)
  - วิเคราะห์ได้หลาย Timeframe หลากหลายระดับ (1m ไปจนถึง 1d)
  - รูปแบบกราฟที่ทำงานแบบระบบเชิงลึกในที่เดียว
  - ระบบจัดการ API Key และจัดการ Custom Asset ผ่านแหล่งต่างๆได้เอง

### 🤖 AI Trading Agents (MCP)
ระบบรองรับเซิร์ฟเวอร์แบบ **Model Context Protocol (MCP)** เพื่อช่วยให้ AI จากภายนอก หรือ Desktop app สามารถกระทำการซื้อขายและจัดการคำสั่งแบบอัตโนมัติ:
- **`mcp_servers/mt5_trading_server.py`**: การซื้อขายทาง MT5 (จำเป็นต้องมี `mt5-bridge` server)
- **`mcp_servers/binance_trading_server.py`**: ซื้อขาย Binance (Spot และ USDS-M Futures)
- **`mcp_servers/bitkub_trading_server.py`**: ซื้อขาย Bitkub (เข้าสู่ระบบด้วย HMAC-SHA256)

เซิร์ฟเวอร์มาตรฐานเหล่านี้สามารถอนุญาตให้ AI (LLMs) เช็คยอดเงิน, ตรวจสอบสถานะการเทรด, และทำการตั้งค่าออเดอร์ หรือปิดการซื้อขายได้โดยตรง

## 📦 การติดตั้ง

### 1. เช็คและเปิดทำงาน Conda Environment

```bash
conda create -n quantagents python=3.11
conda activate quantagents
```

### 2. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
# ส่วนเสริมสำหรับการเชื่อมต่อผ่านแหล่งข้อมูลต่างๆและการสั่งงานแอป
pip install python-binance pandas requests flask yfinance mcp
```

หากพบปัญหาการติดตั้ง TA-lib-python ให้ลอง:

```bash
conda install -c conda-forge ta-lib
```

หรือศึกษา [TA-Lib Python repository](https://github.com/ta-lib/ta-lib-python) สำหรับขั้นตอนการติดตั้งอย่างละเอียด

### 3. ใส่ข้อมูล LLM & Exchange API Keys
คุณสามารถกำหนดค่าการเชื่อมต่อ API LLM ใน Web Interface ภายหลังได้:

![apibox](assets/apibox.png)

หรือกำหนดผ่าน Environment Variable แนะนำให้คัดลอกและดู `.env.sample`:
```bash
# สำหรับ OpenAI
export OPENAI_API_KEY="your_openai_api_key_here"

# สำหรับ Anthropic (Claude)
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"

# สำหรับ Qwen (DashScope)
export DASHSCOPE_API_KEY="your_dashscope_api_key_here"

# Exchange APIs (สำหรับให้ MCP ดำเนินการเทรด หรือระบบหลังบ้าน)
export BINANCE_API_KEY="your_binance_key"
export BINANCE_API_SECRET="your_binance_secret"
export BITKUB_API_KEY="your_bitkub_key"
export BITKUB_API_SECRET="your_bitkub_secret"
```

## 🚀 วิธีใช้งาน

### การเรียกใช้งาน Web Interface เบื้องต้น

```bash
python web_interface.py
```

ระบบจะรันแอปพลิเคชันขึ้นมาที่  `http://127.0.0.1:5000` ทันที

### ขีดความสามารถ Web Interface

1. **การเลือกใช้งาน Asset**: ตรวจสอบหุ้น คริปโต สินค้าโภคภัณฑ์ ต่างๆ จากหน้าควบคุม
2. **การกะเวลาแบบ Timeframe**: สแกนวิเคราะห์ย้อนหลังในระดับตั้งแต่นาที ไปจนถึงระดับรายวัน
3. **วัน/เวลาเริ่มต้น (Date Range)**: ตัดสินใจกำหนดวันที่สแกน
4. **การวิเคราะห์แบบเรียลไทม์**: โหลดและรอการวิเคราะห์ทางเทคนิคไปจนถึงการทำกราฟอัตโนมัติ
5. **การจัดการ API Key**: เปลี่ยนแปลง OpenAI API key เพื่อคำนวณผ่านอินเทอร์เฟซต่างๆ

## 📺 ตัวอย่างเดโม่

![Quick preview](assets/demo.gif)


## 🔧 รายละเอียดการทำงาน

**ข้อสำคัญ**: โมเดลของเราจำเป็นต้องใช้ LLM ที่รองรับการอ่านและเรียนรู้ข้อมูลรูปแบบรูปภาพ เนื่องจากตัวแทนเอเจนต์จะต้องประมวลผลวิเคราะห์การแสดงรูปกราฟต่างๆออกมา

### การทำงานผ่าน Python (API)

เปิดโอกาสให้คุณเรียกใช้ `trading_graph` ภายในโค้ดเพื่อให้ได้สคริปต์อัตโนมัติ โดยสร้าง `TradingGraph()` Object เพื่อเตรียมการส่ง `.invoke()` สำหรับโหลดรายงานการสแกน สามารถดูโค้ดเพิ่มเติมจาก `web_interface.py`:

```python
from trading_graph import TradingGraph

# กำหนดสคริปต์ TradingGraph
trading_graph = TradingGraph()

# เซ็ตข้อมูลเริ่มต้น (Initial State)
initial_state = {
    "kline_data": your_dataframe_dict,
    "analysis_results": None,
    "messages": [],
    "time_frame": "4hour",
    "stock_name": "BTC"
}

# เรียกใช้งานวิเคราะห์
final_state = trading_graph.graph.invoke(initial_state)

# ขอออ่านค่าและรายงานต่างๆผ่าน Console
print(final_state.get("final_trade_decision"))
print(final_state.get("indicator_report"))
print(final_state.get("pattern_report"))
print(final_state.get("trend_report"))
```

### Multi-Exchange CLI Analyzers (การใช้งานผ่านสคริปต์ Command Line)

คุณยังสามารถรันการสแกนวิเคราะห์ผลตอบแทนผ่านระบบอัตโนมัติได้โดยตรงผ่าน Terminal / Command Line โดยไม่ต้องเปิดเว็บ เราได้พัฒนาสคริปต์ CLI แยกสำหรับแต่ละแหล่งข้อมูล ซึ่งสามารถป้อนตัวแปรอาร์กิวเมนต์แบบครอบคลุมสำหรับการรับข้อมูลทั้งแบบระบุ Bars และแบบวันที่:

```bash
# ระบบของ Binance (Spot Market)
python binance_analyze.py --symbol BTCUSDT --timeframe 1h --bars 100

# ระบบของ Bitkub (Thai Public API)
python bitkub_analyze.py --symbol BTC_THB --timeframe 4h --start "2025-01-01" --end "2025-01-31"

# ระบบของ MetaTrader 5 (จำเป็นต้องรันเซิร์ฟเวอร์ mt5-bridge ควบคู่)
python mt5_analyze.py --symbol XAUUSD --timeframe 15m --bars 200 --output report.json
```

**Common CLI Arguments (ตัวแปรพารามิเตอร์ของระบบ):**
- `--symbol`: สัญลักษณ์คู่เหรียญ หรือชื่อหุ้น ที่ต้องการดึง (จำเป็น)
- `--timeframe`: ขนาดความละเอียดแท่งเทียน (ตัวอย่างเช่น: `1m`, `15m`, `1h`, `1d`)
- `--bars`: จำนวนแท่งล่าสุดที่ใช้ดึง (จะถูกประเมินและบังคับใช้ก่อนหากไม่ได้ระบุวันที่)
- `--start` / `--end`: ดึงข้อมูลจากช่วงวันที่และเวลาเฉพาะการเทรดที่ตายตัว (รูปแบบข้อมูล: `YYYY-MM-DD` หรือ `YYYY-MM-DD HH:MM`)
- `--output`: นำส่งผลการวิเคราะห์ให้เซฟตัวเองกลายเป็นไฟล์นามสกุล JSON โดยตรง (ไม่บังคับ)

ผู้ใช้ก็สามารถเข้าไปกำหนดตัวเลือก LLM ด้วยตัวเองในโค้ด `web_interface.py` ได้ด้วย

```python
if provider == "anthropic":
    if not analyzer.config["agent_llm_model"].startswith("claude"):
        analyzer.config["agent_llm_model"] = "claude-haiku-4-5-20251001"
#... และ Provider แบบอื่นๆ
```

หากต้องการการดึงข้อมูลสดๆ เราขอแนะนำว่าให้ใช้ Web Interface เพราะมีกลไกที่ครอบคลุมถึง Yahoo Finance, Binance, MT5 แบบ Built-in

### ตัวเลือกการตั้งค่าล่วงหน้า

ระบบสามารถตั้งค่าผ่าน parameter ต่อไปนี้:

- `agent_llm_model`: ปรับแต่งโมเดลเฉพาะเจาะจงแก่ agent นั้นๆ (ค่าเริ่มต้น: "gpt-4o-mini")
- `graph_llm_model`: ปรับตั้งโมเดลการประมวลผลและการตัดสินใจสั่งงานข้ามระบบ (ค่าเริ่มต้น: "gpt-4o")
- `agent_llm_temperature`: อุณหภูมิตอบสนอง (ค่าเริ่มต้น 0.1)
- `graph_llm_temperature`: อุณหภูมิการตัดสินใจของกราฟหลัก (ค่าเริ่มต้น 0.1)

**หมายเหตุ**: ระบบจะคำนวณ token limit เต็มที่สำหรับการสแกน โดยไม่มีข้อจำกัดเพื่อตัดลดทอนคุณภาพโมเดลแต่อย่างใด
ตรวจสอบการตั้งค่าทั้งหมดได้เพิ่มเติมในไฟล์ `default_config.py`

## 🤝 การมีส่วนร่วม

1. กด Fork โปรเจ็กต์
2. ทำการแบ่งกิ่งโครงสร้าง (Create feature branch)
3. เปลี่ยนแปลงโค้ดของคุณ
4. เขียนขั้นตอนตรวจสอบเข้าไปบ้างถ้าเป็นไปได้ 
5. สั่งส่งคำขอ Pull request เข้ามา 

## 📄 ไลเซนส์

ใช้งานภายใต้สิทธิ์และการคุ้มครอง MIT License - สามารถดูข้อกำหนดต่างๆเพิ่มเติมที่หน้า LICENSE 

## 🔖 Citation (การอ้างอิง)
```
@article{xiong2025quantagent,
  title={QuantAgent: Price-Driven Multi-Agent LLMs for High-Frequency Trading},
  author={Fei Xiong and Xiang Zhang and Aosong Feng and Siqi Sun and Chenyu You},
  journal={arXiv preprint arXiv:2509.09995},
  year={2025}
}
```

## 🙏 เครดิตคำขอบคุณและการอ้างอิงไลบรารี่

This repository was built with the help of the following libraries and frameworks:

- [**LangGraph**](https://github.com/langchain-ai/langgraph)
- [**OpenAI**](https://github.com/openai/openai-python)
- [**Anthropic (Claude)**](https://github.com/anthropics/anthropic-sdk-python)
- [**Qwen**](https://github.com/QwenLM/Qwen)
- [**yfinance**](https://github.com/ranaroussi/yfinance)
- [**python-binance**](https://github.com/sammchardy/python-binance)
- [**Bitkub Official API Docs**](https://github.com/bitkub/bitkub-official-api-docs)
- [**MCP**](https://github.com/modelcontextprotocol/python-sdk)
- [**Flask**](https://github.com/pallets/flask)
- [**TechnicalAnalysisAutomation**](https://github.com/neurotrader888/TechnicalAnalysisAutomation/tree/main)
- [**tvdatafeed**](https://github.com/rongardF/tvdatafeed)

## ⚠️ ข้อจำกัดความรับผิดชอบ

ซอฟต์แวร์นี้จัดทำขึ้นเพื่อการศึกษาและการวิจัยเท่านั้น ไม่ได้มีจุดประสงค์เพื่อให้คำปรึกษาหรือเก็งกำไรทางการเงิน คุณต้องไปศึกษาด้วยตนเองให้รอบเหมาะสมเสมอและควรพิจารณาปรึกษาที่ปรึกษาทางการเงินและกฎหมายเพื่อรับความเสี่ยงที่แท้จริง

## 🐛 ปัญหาหน้างานบ่อยครั้งและการแก้ไข (Troubleshooting)

1. **ปัญหาการติดตั้งระบบ TA-Lib**: แนะนำให้ไปเช็ควิธีการของหน้าเว็บ [Official Repositoryของเขาแบบเจาะจงแทน](https://github.com/ta-lib/ta-lib-python)

2. **ปัญหาเกี่ยวกับ LLM API Key**: แน่ใจว่าคีย์ถูกต้องเมื่อเข้าใน Environment Setting หรือที่ Interface

3. **ปัญหาเรื่องแหล่ง Data Fetching**: การหาค่าข้อมูลบางส่วนใน Yahoo, Binance, Bitkub อาจไม่ครอบคลุม 100% ควรทดสอบตรวจสอบรายชื่อ Asset ว่ายังมีตัวตนจริงๆ และข้อมูลครบหรือไม่

4. **ปัญหาความจำประมวลผลข้อมูล**: หากต้องการดึงข้อมูลใหญ่มากๆ ให้เปลี่ยนไปใช้ Timeframe ขนาดระดับใหญ่แทน หรือปรับแก้ให้มีขนาดวิเคราะห์ที่ลดเวลา Date Range ลงมาจาก 1d เป็น 2-5 bars

## 📧 ติดต่อเรา

หากต้องการรายงานปัญหา แชร์ข้อเสนอแนะ ติดต่อเราได้ที่:

**อีเมล**: [chenyu.you@stonybrook.edu](mailto:chenyu.you@stonybrook.edu), [siqisun@fudan.edu.cn](mailto:siqisun@fudan.edu.cn)


## ลำดับเวลาความนิยม (Star History)

[![Star History Chart](https://api.star-history.com/svg?repos=Y-Research-SBU/QuantAgent&type=Date)](https://www.star-history.com/#Y-Research-SBU/QuantAgent&Date)
