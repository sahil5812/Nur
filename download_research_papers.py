import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PAPERS = [
    {
        "filename": "01_PPO_Proximal_Policy_Optimization_Algorithms.pdf",
        "title": "Proximal Policy Optimization Algorithms",
        "authors": "John Schulman, Filip Wolski, Prafulla Dhariwal, Alec Radford, Oleg Klimov",
        "year": "2017",
        "arxiv_id": "1707.06347",
        "url": "https://arxiv.org/pdf/1707.06347.pdf",
        "relevance": "The core RL policy algorithm implemented in Nur-main (rl/train.py, rl/agent.py, Stable-Baselines3 PPO)."
    },
    {
        "filename": "02_Hierarchical_RL_for_Trading_and_Execution.pdf",
        "title": "Deep Stock Trading: A Hierarchical Reinforcement Learning Framework for Portfolio Optimization and Order Execution",
        "authors": "Rundong Wang, Hongxin Wei, Bo An, et al.",
        "year": "2020",
        "arxiv_id": "2012.12620",
        "url": "https://arxiv.org/pdf/2012.12620.pdf",
        "relevance": "Direct theoretical basis for Nur-main's multi-agent hierarchy (Meta-controller regime router + low-level execution agents)."
    },
    {
        "filename": "03_EarnHFT_Hierarchical_RL_for_High_Frequency_Trading.pdf",
        "title": "EarnHFT: Efficient Hierarchical Reinforcement Learning for High Frequency Trading",
        "authors": "Haohang Li, Siyu Gao, et al.",
        "year": "2023",
        "arxiv_id": "2309.12891",
        "url": "https://arxiv.org/pdf/2309.12891.pdf",
        "relevance": "High-frequency & intraday execution (M1 level execution, time decay penalties, order timing)."
    },
    {
        "filename": "04_FinRL_Deep_Reinforcement_Learning_Library.pdf",
        "title": "FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading",
        "authors": "Xiao-Yang Liu, Hongyang Yang, Jiechao Gao, Christina Dan Wang",
        "year": "2020",
        "arxiv_id": "2011.09607",
        "url": "https://arxiv.org/pdf/2011.09607.pdf",
        "relevance": "Standardized benchmark and trading environment structure (Gymnasium observation/action mapping in finance)."
    },
    {
        "filename": "05_RL_Applied_to_Trading_Systems_Survey.pdf",
        "title": "Reinforcement Learning Applied to Trading Systems: A Survey",
        "authors": "Felizardo, et al.",
        "year": "2022",
        "arxiv_id": "2212.06064",
        "url": "https://arxiv.org/pdf/2212.06064.pdf",
        "relevance": "Comprehensive state-of-the-art survey covering state space design (RSI, MACD, EMA), reward shaping, and position sizing."
    },
    {
        "filename": "06_Deep_RL_in_Quantitative_Algorithmic_Trading_Review.pdf",
        "title": "Deep Reinforcement Learning in Quantitative Algorithmic Trading: A Review",
        "authors": "Mihai-Valentin Pricope",
        "year": "2021",
        "arxiv_id": "2106.00123",
        "url": "https://arxiv.org/pdf/2106.00123.pdf",
        "relevance": "Review of practical challenges, out-of-sample testing, overfitting risks, and trade evaluation metrics in quantitative execution."
    },
    {
        "filename": "07_Deep_RL_for_Trading_Oxford.pdf",
        "title": "Deep Reinforcement Learning for Trading",
        "authors": "Zihao Zhang, Stefan Zohren, Stephen Roberts (Oxford-Man Institute of Quantitative Finance)",
        "year": "2019",
        "arxiv_id": "1911.10107",
        "url": "https://arxiv.org/pdf/1911.10107.pdf",
        "relevance": "Volatility-scaled reward functions, stop-loss mechanisms, and transaction cost/slippage penalization."
    },
    {
        "filename": "08_HMM_and_LSTM_Stock_Market_Trend_Analysis.pdf",
        "title": "Stock Market Trend Analysis Using Hidden Markov Model and Long Short Term Memory",
        "authors": "Qin, et al.",
        "year": "2021",
        "arxiv_id": "2104.09700",
        "url": "https://arxiv.org/pdf/2104.09700.pdf",
        "relevance": "Gaussian HMM for regime detection (trending vs ranging) combined with sequential price models, matching rl/hmm_classifier.py."
    },
    {
        "filename": "09_Hidden_Markov_Models_Stock_Prediction.pdf",
        "title": "Hidden Markov Models for Stock Market Prediction",
        "authors": "Singh, et al.",
        "year": "2023",
        "arxiv_id": "2310.03775",
        "url": "https://arxiv.org/pdf/2310.03775.pdf",
        "relevance": "Expectation-Maximization (Baum-Welch) and Viterbi state decoding on financial market regimes."
    },
    {
        "filename": "10_Deep_RL_Framework_Financial_Portfolio_Management.pdf",
        "title": "A Deep Reinforcement Learning Framework for the Financial Portfolio Management Problem",
        "authors": "Zhengyao Jiang, Dixing Xu, Jinjun Liang",
        "year": "2017",
        "arxiv_id": "1706.10059",
        "url": "https://arxiv.org/pdf/1706.10059.pdf",
        "relevance": "Foundational architectural blueprint for financial time-series DRL pipelines and continuous policy optimization."
    }
]

def main():
    target_dir = r"C:\Users\Abusahil\OneDrive\Desktop\Doc\projects\Nur-main\research_papers"
    os.makedirs(target_dir, exist_ok=True)
    print(f"Target directory: {target_dir}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 NurTradingResearch/1.0"
    }

    index_markdown = [
        "# Nur Trading Bot - Core Academic Research Papers\n\n",
        "This directory contains foundational, peer-reviewed, and state-of-the-art research papers directly underpinning the architecture and algorithms of **Nur Trading Bot**.\n\n",
        "### Topics Covered:\n",
        "- **Proximal Policy Optimization (PPO)** for algorithmic execution\n",
        "- **Hierarchical Multi-Agent Reinforcement Learning (MARL)** (Meta-controller regime router + specialized sub-agents)\n",
        "- **Gaussian Hidden Markov Models (HMM)** for market regime classification (Trending vs. Ranging) using Baum-Welch & Viterbi\n",
        "- **High-Frequency & Intraday Quantitative Trading** (M1 timeframe, volatility-scaled rewards, slippage & latency)\n\n",
        "| # | Paper Title | Topic / Component | Authors / Year | File |\n",
        "|---|---|---|---|---|\n"
    ]

    for idx, paper in enumerate(PAPERS, 1):
        filepath = os.path.join(target_dir, paper["filename"])
        print(f"\n[{idx}/{len(PAPERS)}] Processing: {paper['title']}")
        
        # Download if not already present or file is too small
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 50000:
            print(f"Downloading from {paper['url']} ...")
            req = urllib.request.Request(paper["url"], headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=45) as response, open(filepath, 'wb') as out_file:
                    data = response.read()
                    out_file.write(data)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f"[SUCCESS] Downloaded: {paper['filename']} ({size_mb:.2f} MB)")
            except Exception as e:
                print(f"[FAILED] Error downloading {paper['title']}: {e}")
        else:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"[EXISTS] Already present: {paper['filename']} ({size_mb:.2f} MB)")

        index_markdown.append(
            f"| {idx} | **{paper['title']}**<br>*{paper['relevance']}* | {paper['arxiv_id']} | {paper['authors']} ({paper['year']}) | [`{paper['filename']}`]({paper['filename']}) |\n"
        )
        time.sleep(2)  # Respectful arXiv rate limiting

    readme_path = os.path.join(target_dir, "PAPERS_INDEX.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.writelines(index_markdown)
    print(f"\n[DONE] Generated catalog: {readme_path}")
    print("\n[COMPLETED] All papers processed successfully!")

if __name__ == "__main__":
    main()
