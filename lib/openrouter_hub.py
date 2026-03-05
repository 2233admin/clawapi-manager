#!/usr/bin/env python3
"""
FreeClaw OpenRouter Hub - 免费模型自动发现 + 负载均衡
输入 API Key → 自动拉取所有免费模型 → 轮询/加权负载均衡
"""

import os
import sys
import json
import time
import random
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

CACHE_FILE = os.path.join(DATA_DIR, 'openrouter_free_models.json')
STATS_FILE = os.path.join(DATA_DIR, 'openrouter_stats.json')
API_BASE = "https://openrouter.ai/api/v1"
CACHE_TTL = 3600  # 1小时刷新一次免费模型列表


class OpenRouterHub:
    """OpenRouter 免费模型中心 + 负载均衡"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY', '')
        self.free_models: List[Dict] = []
        self.stats: Dict = self._load_stats()
        self._load_cache()

    # === 免费模型自动发现 ===

    def discover_free_models(self, force: bool = False) -> List[Dict]:
        """从 OpenRouter API 自动发现所有免费模型"""
        if not force and self.free_models and not self._cache_expired():
            return self.free_models

        if not self.api_key:
            print("Warning: OPENROUTER_API_KEY not set, using cached data")
            return self.free_models

        try:
            resp = requests.get(
                f"{API_BASE}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15
            )
            resp.raise_for_status()
            all_models = resp.json().get('data', [])

            # 筛选免费模型（pricing.prompt == "0" 或 pricing 为 0）
            free = []
            for m in all_models:
                pricing = m.get('pricing', {})
                prompt_cost = float(pricing.get('prompt', '1') or '1')
                completion_cost = float(pricing.get('completion', '1') or '1')

                if prompt_cost == 0 and completion_cost == 0:
                    free.append({
                        'id': m['id'],
                        'name': m.get('name', m['id']),
                        'context_length': m.get('context_length', 0),
                        'top_provider': m.get('top_provider', {}).get('max_completion_tokens', 0),
                        'architecture': m.get('architecture', {}).get('modality', 'text'),
                        'per_request_limits': m.get('per_request_limits', {}),
                    })

            # 按 context_length 排序（大的优先）
            free.sort(key=lambda x: x.get('context_length', 0), reverse=True)

            self.free_models = free
            self._save_cache()
            return free

        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to fetch models: {e}")
            return self.free_models

    def _cache_expired(self) -> bool:
        cache_file = Path(CACHE_FILE)
        if not cache_file.exists():
            return True
        age = time.time() - cache_file.stat().st_mtime
        return age > CACHE_TTL

    def _load_cache(self):
        if Path(CACHE_FILE).exists():
            try:
                with open(CACHE_FILE) as f:
                    data = json.load(f)
                self.free_models = data.get('models', [])
            except (json.JSONDecodeError, KeyError):
                self.free_models = []

    def _save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump({
                'models': self.free_models,
                'updated_at': datetime.now().isoformat(),
                'count': len(self.free_models),
            }, f, indent=2)

    # === 负载均衡 ===

    def get_model(self, strategy: str = 'weighted') -> Optional[str]:
        """负载均衡选择免费模型

        Strategies:
          - round_robin: 轮询
          - weighted: 按成功率加权（默认）
          - random: 随机
          - context: 选 context 最大的
          - least_used: 选使用次数最少的
        """
        models = self.discover_free_models()
        if not models:
            return None

        if strategy == 'round_robin':
            return self._round_robin(models)
        elif strategy == 'random':
            return random.choice(models)['id']
        elif strategy == 'context':
            return models[0]['id']  # 已按 context_length 降序
        elif strategy == 'least_used':
            return self._least_used(models)
        else:  # weighted
            return self._weighted_select(models)

    def _round_robin(self, models: List[Dict]) -> str:
        idx = self.stats.get('rr_index', 0)
        model_id = models[idx % len(models)]['id']
        self.stats['rr_index'] = (idx + 1) % len(models)
        self._save_stats()
        return model_id

    def _least_used(self, models: List[Dict]) -> str:
        usage = self.stats.get('usage', {})
        min_count = float('inf')
        best = models[0]['id']
        for m in models:
            count = usage.get(m['id'], {}).get('total', 0)
            if count < min_count:
                min_count = count
                best = m['id']
        return best

    def _weighted_select(self, models: List[Dict]) -> str:
        """按成功率 + context 大小加权选择"""
        usage = self.stats.get('usage', {})
        weights = []

        for m in models:
            model_stats = usage.get(m['id'], {})
            total = model_stats.get('total', 0)
            success = model_stats.get('success', 0)

            # 成功率（新模型默认 0.8）
            success_rate = success / max(total, 1) if total > 5 else 0.8

            # context 加成（归一化到 0-1）
            max_ctx = max(x.get('context_length', 1) for x in models)
            ctx_score = m.get('context_length', 0) / max(max_ctx, 1)

            # 综合权重 = 成功率 70% + context 30%
            weight = success_rate * 0.7 + ctx_score * 0.3
            weights.append((m['id'], max(weight, 0.01)))

        # 加权随机选择
        total_weight = sum(w for _, w in weights)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for model_id, w in weights:
            cumulative += w
            if r <= cumulative:
                return model_id

        return weights[-1][0]

    # === 统计追踪 ===

    def record_success(self, model_id: str, latency_ms: float = 0):
        """记录成功调用"""
        self._record(model_id, True, latency_ms)

    def record_failure(self, model_id: str, error: str = ""):
        """记录失败调用"""
        self._record(model_id, False, 0, error)

    def _record(self, model_id: str, success: bool,
                latency_ms: float = 0, error: str = ""):
        usage = self.stats.setdefault('usage', {})
        m = usage.setdefault(model_id, {
            'total': 0, 'success': 0, 'fail': 0,
            'avg_latency_ms': 0, 'last_error': '', 'last_used': ''
        })

        m['total'] += 1
        if success:
            m['success'] += 1
            # 移动平均 latency
            old_avg = m.get('avg_latency_ms', 0)
            m['avg_latency_ms'] = round(old_avg * 0.8 + latency_ms * 0.2, 1)
        else:
            m['fail'] += 1
            m['last_error'] = error[:200]

        m['last_used'] = datetime.now().isoformat()

        # 自动禁用连续失败 5 次的模型
        recent_fails = m['fail']
        if m['total'] > 10 and (m['fail'] / m['total']) > 0.5:
            m['disabled'] = True
            # 从 free_models 中移除
            self.free_models = [x for x in self.free_models if x['id'] != model_id]

        self._save_stats()

    def _load_stats(self) -> dict:
        if Path(STATS_FILE).exists():
            try:
                with open(STATS_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass
        return {'usage': {}, 'rr_index': 0}

    def _save_stats(self):
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2)

    # === 账户信息 ===

    def get_account_info(self) -> Dict:
        """查询 OpenRouter 账户余额和使用情况"""
        if not self.api_key:
            return {'error': 'API key not set'}
        try:
            # Credits
            resp = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json().get('data', {})
            return {
                'label': data.get('label', ''),
                'credits': data.get('limit', 0),
                'usage': data.get('usage', 0),
                'remaining': (data.get('limit', 0) or 0) - (data.get('usage', 0) or 0),
                'rate_limit': data.get('rate_limit', {}),
            }
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

    # === 显示 ===

    def show_free_models(self):
        """显示所有免费模型"""
        models = self.discover_free_models()
        usage = self.stats.get('usage', {})

        print(f"\nFreeClaw - OpenRouter Free Models ({len(models)})")
        print("=" * 80)
        print(f"{'#':>3} {'Model ID':<45} {'Context':>8} {'Calls':>6} {'Success':>8}")
        print("-" * 80)

        for i, m in enumerate(models, 1):
            model_id = m['id']
            ctx = f"{m.get('context_length', 0) // 1024}K"
            u = usage.get(model_id, {})
            total = u.get('total', 0)
            success = u.get('success', 0)
            rate = f"{success/total*100:.0f}%" if total > 0 else "-"
            disabled = " [DISABLED]" if u.get('disabled') else ""

            print(f"{i:>3} {model_id:<45} {ctx:>8} {total:>6} {rate:>8}{disabled}")

        print(f"\nTotal: {len(models)} free models available")

    def show_stats(self):
        """显示负载均衡统计"""
        usage = self.stats.get('usage', {})
        if not usage:
            print("No usage data yet")
            return

        total_calls = sum(u.get('total', 0) for u in usage.values())
        total_success = sum(u.get('success', 0) for u in usage.values())
        total_fail = sum(u.get('fail', 0) for u in usage.values())

        print(f"\nFreeClaw Load Balancer Stats")
        print("=" * 60)
        print(f"Total Calls:    {total_calls}")
        print(f"Success:        {total_success} ({total_success/max(total_calls,1)*100:.1f}%)")
        print(f"Failed:         {total_fail}")
        print(f"Models Used:    {len(usage)}")
        print(f"Free Models:    {len(self.free_models)}")

        # Top 5 most used
        sorted_usage = sorted(usage.items(), key=lambda x: x[1].get('total', 0), reverse=True)
        print(f"\nTop 5 Models:")
        for model_id, u in sorted_usage[:5]:
            total = u.get('total', 0)
            rate = u.get('success', 0) / max(total, 1) * 100
            latency = u.get('avg_latency_ms', 0)
            print(f"  {model_id:<40} calls={total:>5} success={rate:.0f}% latency={latency:.0f}ms")

    def show_account(self):
        """显示账户信息"""
        info = self.get_account_info()
        if 'error' in info:
            print(f"Error: {info['error']}")
            return

        print(f"\nOpenRouter Account")
        print("=" * 40)
        print(f"Label:      {info.get('label', 'N/A')}")
        print(f"Credits:    ${info.get('credits', 0):.4f}")
        print(f"Usage:      ${info.get('usage', 0):.4f}")
        print(f"Remaining:  ${info.get('remaining', 0):.4f}")

        # 省钱提示
        usage = self.stats.get('usage', {})
        free_calls = sum(u.get('total', 0) for u in usage.values())
        if free_calls > 0:
            # 假设每次调用平均省 $0.001
            estimated_savings = free_calls * 0.001
            print(f"\nEstimated savings from free routing: ~${estimated_savings:.2f}")
            print(f"Free API calls made: {free_calls}")


def setup_api_key():
    """交互式设置 API Key"""
    print("\nFreeClaw OpenRouter Setup")
    print("=" * 40)
    print("Get your free API key at: https://openrouter.ai/keys")
    print()

    key = input("Enter OpenRouter API Key: ").strip()
    if not key:
        print("Cancelled")
        return

    # 验证 key
    hub = OpenRouterHub(api_key=key)
    info = hub.get_account_info()

    if 'error' in info:
        print(f"\nFailed to verify key: {info['error']}")
        return

    print(f"\nKey verified! Label: {info.get('label', 'N/A')}")

    # 保存到环境
    env_file = Path.home() / ".freeclaw_env"
    with open(env_file, 'w') as f:
        f.write(f"OPENROUTER_API_KEY={key}\n")
    print(f"Key saved to {env_file}")

    # 立即发现免费模型
    models = hub.discover_free_models(force=True)
    print(f"\nDiscovered {len(models)} free models!")
    hub.show_free_models()


def main():
    if len(sys.argv) < 2:
        print("\nFreeClaw OpenRouter Hub")
        print("\nSetup:")
        print("  setup                    Set API key & discover free models")
        print("\nModels:")
        print("  discover [--force]       Discover free models")
        print("  list                     List all free models")
        print("  pick [strategy]          Pick a model (weighted/round_robin/random/context/least_used)")
        print("\nStats:")
        print("  stats                    Show load balancer stats")
        print("  account                  Show account & savings info")
        print("  record-ok <model_id>     Record success")
        print("  record-fail <model_id>   Record failure")
        return

    cmd = sys.argv[1]
    hub = OpenRouterHub()

    if cmd == 'setup':
        setup_api_key()
    elif cmd == 'discover':
        force = '--force' in sys.argv
        models = hub.discover_free_models(force=force)
        print(f"Found {len(models)} free models")
        hub.show_free_models()
    elif cmd == 'list':
        hub.show_free_models()
    elif cmd == 'pick':
        strategy = sys.argv[2] if len(sys.argv) > 2 else 'weighted'
        model = hub.get_model(strategy)
        if model:
            print(json.dumps({'model': model, 'strategy': strategy}, indent=2))
        else:
            print("No free models available. Run: openrouter_hub.py discover")
    elif cmd == 'stats':
        hub.show_stats()
    elif cmd == 'account':
        hub.show_account()
    elif cmd == 'record-ok':
        model_id = sys.argv[2]
        latency = float(sys.argv[3]) if len(sys.argv) > 3 else 0
        hub.record_success(model_id, latency)
        print(f"Recorded success: {model_id}")
    elif cmd == 'record-fail':
        model_id = sys.argv[2]
        error = sys.argv[3] if len(sys.argv) > 3 else ""
        hub.record_failure(model_id, error)
        print(f"Recorded failure: {model_id}")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()
