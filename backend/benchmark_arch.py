
import time
import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to sys.path so we can import from 'app'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.services.redis_cache import redis_cache
from app.services.rss.cache_service import cache_service
from app.services.rss.aggregator import aggregate_all_feeds
from app.db import SessionLocal
from app.repositories.rss_repository import RssItemRepository

def benchmark_current_cache_hit():
    """Measures latency when fetching from Redis."""
    # Use a common key or create a dummy one
    test_key = "feed:none:true:50:0:none"
    
    # Ensure data exists for the hit benchmark
    dummy_data = {"items": [], "total_items": 0, "sources": [], "fetched_at": "2024-01-01"}
    redis_cache.set(test_key, dummy_data, ttl_seconds=300)
    
    # Verify it was set
    if not redis_cache.get(test_key):
        return None

    start = time.perf_counter()
    data = redis_cache.get(test_key)
    end = time.perf_counter()
    
    latency_ms = (end - start) * 1000
    return latency_ms if data else None

def benchmark_current_cache_miss_db():
    """Measures latency when fetching from PostgreSQL (bypassing Redis)."""
    start = time.perf_counter()
    # This calls the DB repository logic
    data = cache_service.get_cached_feed(category=None, limit=50, offset=0)
    end = time.perf_counter()
    
    latency_ms = (end - start) * 1000
    return latency_ms

def benchmark_alternative_sync_aggregator():
    """
    Measures latency for the Synchronous Monolithic pattern.
    Warning: This makes actual external HTTP calls. 
    We limit to a small number of feeds to avoid hitting rate limits.
    """
    print("\n[!] Starting Synchronous Aggregation (Alternative Architecture)...")
    print("    This fetches live data from RSS feeds and external APIs. Please wait...")
    
    start = time.perf_counter()
    # We call the full aggregator as it would happen in a synchronous monolith
    # limit_per_feed=5 to keep it relatively fast but realistic
    try:
        data = aggregate_all_feeds(limit_per_feed=5)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        return latency_ms
    except Exception as e:
        print(f"    Error during sync fetch: {e}")
        return None

def run_benchmarks():
    import statistics
    
    print("="*85)
    print("UniCompass Architectural Quantitative Analysis")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*85)

    # 1. Cache Hit (50 runs)
    hit_latencies = []
    print("\n[!] Running Cache Hit benchmark (50 runs)...")
    for _ in range(50):
        lat = benchmark_current_cache_hit()
        if lat: hit_latencies.append(lat)
    
    if hit_latencies:
        hit_latencies.sort()
        n_hit = len(hit_latencies)
        hit_mean = sum(hit_latencies)/n_hit
        hit_p50 = statistics.median(hit_latencies)
        hit_p95 = hit_latencies[int(n_hit * 0.95)]
        hit_p99 = hit_latencies[min(int(n_hit * 0.99), n_hit - 1)]
        hit_max = hit_latencies[-1]
        hit_tp = 1000.0 / hit_mean
    else:
        hit_mean = hit_p50 = hit_p95 = hit_p99 = hit_max = hit_tp = 0

    # 2. Cache Miss (20 runs)
    db_latencies = []
    print("[!] Running Cache Miss (PostgreSQL) benchmark (20 runs)...")
    for _ in range(20):
        db_latencies.append(benchmark_current_cache_miss_db())
    
    db_latencies.sort()
    n_db = len(db_latencies)
    db_mean = sum(db_latencies)/n_db
    db_p50 = statistics.median(db_latencies)
    db_p95 = db_latencies[int(n_db * 0.95)]
    db_p99 = db_latencies[min(int(n_db * 0.99), n_db - 1)]
    db_max = db_latencies[-1]
    db_tp = 1000.0 / db_mean

    # 3. Sync Monolith (1 run)
    sync_lat = benchmark_alternative_sync_aggregator()
    sync_mean = sync_lat if sync_lat else 0
    sync_max = sync_lat if sync_lat else 0
    sync_tp = 1000.0 / sync_lat if sync_lat else 0

    print("\n" + "="*90)
    print(f"{'Metric':<18} | {'Cache Hit (Arch A)':<20} | {'Cache Miss (Arch A)':<20} | {'Sync Monolith (Arch B)':<20}")
    print("-" * 90)
    
    print(f"{'Mean':<18} | {hit_mean:>17.2f} ms | {db_mean:>17.2f} ms | {sync_mean:>17.2f} ms")
    print(f"{'p50 (Median)':<18} | {hit_p50:>17.2f} ms | {db_p50:>17.2f} ms | {'N/A':>20}")
    print(f"{'p95':<18} | {hit_p95:>17.2f} ms | {db_p95:>17.2f} ms | {'N/A':>20}")
    print(f"{'p99':<18} | {hit_p99:>17.2f} ms | {db_p99:>17.2f} ms | {'N/A':>20}")
    print(f"{'Max':<18} | {hit_max:>17.2f} ms | {db_max:>17.2f} ms | {sync_max:>17.2f} ms")
    print("-" * 90)
    print(f"{'Throughput':<18} | {hit_tp:>14.2f} req/s | {db_tp:>14.2f} req/s | {sync_tp:>14.2f} req/s")
    print("=" * 90)

    if sync_mean > 0 and hit_mean > 0:
        speedup = sync_mean / hit_mean
        throughput_increase = hit_tp / sync_tp
        print(f"\nCONCLUSION:")
        print(f"  - Latency: Cache Hit is {speedup:,.1f}x faster than Sync Monolith.")
        print(f"  - Throughput: Cache Hit handles {throughput_increase:,.1f}x more requests per second.")
    
    print("="*90)

if __name__ == "__main__":
    run_benchmarks()
