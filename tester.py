#!/usr/bin/env python3
"""
Interactive API Load Tester
A tool for load testing API endpoints with configurable parameters.
Supports extreme load testing with asyncio and multiprocessing.
"""

import asyncio
import aiohttp
import json
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any
import random
import sys
from urllib.parse import urlparse
import statistics
from tqdm.asyncio import tqdm
from tqdm import tqdm as sync_tqdm
import numpy as np

# Predefined list of User-Agent strings for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]

class APILoadTester:
    def __init__(self):
        self.url = ""
        self.method = ""
        self.request_body = None
        self.requests_per_second = 0
        self.total_requests = 0
        self.use_random_user_agent = False
        self.results = []
        self.lock = asyncio.Lock()
        self.session = None
    
    def get_user_input(self) -> None:
        """Collect all required parameters from the user."""
        print("=" * 50)
        print("API Load Tester")
        print("=" * 50)
        
        # Get API URL
        while True:
            self.url = input("Enter API URL (e.g., https://example.com/api): ").strip()
            if self.url:
                # Validate URL format
                parsed = urlparse(self.url)
                if parsed.scheme and parsed.netloc:
                    break
                else:
                    print("Invalid URL format. Please include http:// or https://")
            else:
                print("URL cannot be empty.")
        
        # Get HTTP method
        while True:
            method = input("Enter HTTP method (GET/POST/PUT/DELETE): ").strip().upper()
            if method in ['GET', 'POST', 'PUT', 'DELETE']:
                self.method = method
                break
            else:
                print("Invalid method. Please enter GET, POST, PUT, or DELETE.")
        
        # Get request body for POST/PUT methods
        if self.method in ['POST', 'PUT']:
            body_input = input("Enter request body (JSON format, or press Enter for empty): ").strip()
            if body_input:
                try:
                    self.request_body = json.loads(body_input)
                except json.JSONDecodeError:
                    print("Invalid JSON format. Using empty body.")
                    self.request_body = {}
            else:
                self.request_body = {}
        
        # Get requests per second
        while True:
            try:
                rps = int(input("Enter number of requests per second: "))
                if rps > 0:
                    self.requests_per_second = rps
                    break
                else:
                    print("Requests per second must be greater than 0.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get total number of requests
        while True:
            try:
                total = int(input("Enter total number of requests to send: "))
                if total > 0:
                    self.total_requests = total
                    break
                else:
                    print("Total requests must be greater than 0.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get User-Agent preference
        while True:
            ua_choice = input("Use random User-Agent headers? (yes/no): ").strip().lower()
            if ua_choice in ['yes', 'y']:
                self.use_random_user_agent = True
                break
            elif ua_choice in ['no', 'n']:
                self.use_random_user_agent = False
                break
            else:
                print("Please enter 'yes' or 'no'.")
    
    async def make_request(self, request_id: int) -> Tuple[int, int, float, str]:
        """
        Make a single HTTP request and return the results.
        
        Returns:
            Tuple of (request_id, status_code, response_time, error_message)
        """
        try:
            # Prepare headers
            headers = {'Content-Type': 'application/json'}
            if self.use_random_user_agent:
                headers['User-Agent'] = random.choice(USER_AGENTS)
            
            # Record start time
            start_time = time.time()
            
            # Make the request
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.request(
                method=self.method,
                url=self.url,
                headers=headers,
                json=self.request_body if self.method in ['POST', 'PUT'] else None,
                timeout=timeout
            ) as response:
                # Calculate response time
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                return request_id, response.status, response_time, ""
            
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return request_id, 0, response_time, "Timeout"
        except aiohttp.ClientConnectionError:
            response_time = (time.time() - start_time) * 1000
            return request_id, 0, response_time, "Connection Error"
        except aiohttp.ClientError as e:
            response_time = (time.time() - start_time) * 1000
            return request_id, 0, response_time, f"Client Error: {str(e)}"
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return request_id, 0, response_time, f"Unexpected Error: {str(e)}"
    
    async def print_result(self, request_id: int, status_code: int, response_time: float, error: str) -> None:
        """Print the result of a single request."""
        async with self.lock:
            # Store result for summary
            self.results.append({
                'id': request_id,
                'status_code': status_code,
                'response_time': response_time,
                'error': error,
                'timestamp': time.time()
            })
    
    def print_summary(self) -> None:
        """Print a comprehensive summary of all requests with advanced statistics."""
        print("\n" + "=" * 70)
        print("ADVANCED LOAD TEST SUMMARY")
        print("=" * 70)
        
        if not self.results:
            print("No results to display.")
            return
        
        # Calculate basic statistics
        total_requests = len(self.results)
        successful_requests = len([r for r in self.results if r['status_code'] > 0])
        failed_requests = total_requests - successful_requests
        
        response_times = [r['response_time'] for r in self.results if r['status_code'] > 0]
        all_response_times = [r['response_time'] for r in self.results]
        
        # Calculate test duration
        if self.results:
            timestamps = [r['timestamp'] for r in self.results]
            test_duration = max(timestamps) - min(timestamps)
            actual_rps = total_requests / test_duration if test_duration > 0 else 0
        else:
            test_duration = 0
            actual_rps = 0
        
        # Basic Statistics
        print(f"📊 BASIC STATISTICS")
        print(f"   Total Requests: {total_requests:,}")
        print(f"   Successful: {successful_requests:,}")
        print(f"   Failed: {failed_requests:,}")
        print(f"   Success Rate: {(successful_requests/total_requests)*100:.2f}%")
        print(f"   Test Duration: {test_duration:.2f} seconds")
        print(f"   Target RPS: {self.requests_per_second:,}")
        print(f"   Actual RPS: {actual_rps:.2f}")
        
        # Response Time Statistics
        if response_times:
            print(f"\n⏱️  RESPONSE TIME STATISTICS (Successful Requests)")
            print(f"   Count: {len(response_times):,}")
            print(f"   Average: {statistics.mean(response_times):.2f}ms")
            print(f"   Median: {statistics.median(response_times):.2f}ms")
            print(f"   Min: {min(response_times):.2f}ms")
            print(f"   Max: {max(response_times):.2f}ms")
            print(f"   Std Dev: {statistics.stdev(response_times) if len(response_times) > 1 else 0:.2f}ms")
            
            # Percentiles
            sorted_times = sorted(response_times)
            percentiles = [50, 75, 90, 95, 99]
            print(f"\n📈 PERCENTILES")
            for p in percentiles:
                idx = int((p / 100) * len(sorted_times)) - 1
                if idx < 0:
                    idx = 0
                print(f"   P{p}: {sorted_times[idx]:.2f}ms")
        
        # Throughput Analysis
        if test_duration > 0:
            print(f"\n🚀 THROUGHPUT ANALYSIS")
            print(f"   Requests/Second: {actual_rps:.2f}")
            print(f"   Requests/Minute: {actual_rps * 60:.2f}")
            print(f"   Data Points/Second: {len(self.results) / test_duration:.2f}")
            
            # Calculate throughput efficiency
            efficiency = (actual_rps / self.requests_per_second) * 100 if self.requests_per_second > 0 else 0
            print(f"   Throughput Efficiency: {efficiency:.1f}%")
        
        # Status code distribution
        status_codes = {}
        for result in self.results:
            code = result['status_code']
            if code > 0:
                status_codes[code] = status_codes.get(code, 0) + 1
        
        if status_codes:
            print(f"\n📋 STATUS CODE DISTRIBUTION")
            for code, count in sorted(status_codes.items()):
                percentage = (count / total_requests) * 100
                print(f"   {code}: {count:,} requests ({percentage:.1f}%)")
        
        # Error distribution
        errors = {}
        for result in self.results:
            if result['error']:
                error_type = result['error'].split(':')[0]  # Get error type
                errors[error_type] = errors.get(error_type, 0) + 1
        
        if errors:
            print(f"\n❌ ERROR DISTRIBUTION")
            for error, count in sorted(errors.items()):
                percentage = (count / total_requests) * 100
                print(f"   {error}: {count:,} requests ({percentage:.1f}%)")
        
        # Performance Analysis
        if all_response_times:
            print(f"\n⚡ PERFORMANCE ANALYSIS")
            fast_requests = len([t for t in all_response_times if t < 100])  # < 100ms
            medium_requests = len([t for t in all_response_times if 100 <= t < 500])  # 100-500ms
            slow_requests = len([t for t in all_response_times if t >= 500])  # >= 500ms
            
            print(f"   Fast (< 100ms): {fast_requests:,} ({(fast_requests/total_requests)*100:.1f}%)")
            print(f"   Medium (100-500ms): {medium_requests:,} ({(medium_requests/total_requests)*100:.1f}%)")
            print(f"   Slow (>= 500ms): {slow_requests:,} ({(slow_requests/total_requests)*100:.1f}%)")
        
        print("=" * 70)
    
    async def run_load_test(self) -> None:
        """Execute the load test with the specified parameters using asyncio."""
        print(f"\n🚀 Starting advanced load test...")
        print(f"   URL: {self.url}")
        print(f"   Method: {self.method}")
        print(f"   Target RPS: {self.requests_per_second:,}")
        print(f"   Total requests: {self.total_requests:,}")
        print(f"   Random User-Agent: {'Yes' if self.use_random_user_agent else 'No'}")
        print("-" * 70)
        
        # Calculate timing and concurrency
        if self.requests_per_second >= 100:
            # For high RPS, use batch processing
            batch_size = min(self.requests_per_second, 1000)
            delay_between_batches = 1.0
        else:
            # For lower RPS, use individual request timing
            batch_size = self.requests_per_second
            delay_between_batches = 1.0
        
        # Create aiohttp session with appropriate limits
        connector = aiohttp.TCPConnector(
            limit=min(self.requests_per_second * 2, 2000),  # Connection pool size
            limit_per_host=min(self.requests_per_second, 1000),
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
        try:
            start_time = time.time()
            
            # Create progress bar
            with tqdm(total=self.total_requests, desc="🔄 Processing requests", 
                     unit="req", unit_scale=True, dynamic_ncols=True) as pbar:
                
                # Process requests in batches
                for batch_start in range(0, self.total_requests, batch_size):
                    batch_end = min(batch_start + batch_size, self.total_requests)
                    batch_requests = list(range(batch_start + 1, batch_end + 1))
                    
                    # Create semaphore to limit concurrent requests
                    semaphore = asyncio.Semaphore(min(len(batch_requests), 1000))
                    
                    async def limited_request(request_id):
                        async with semaphore:
                            result = await self.make_request(request_id)
                            await self.print_result(*result)
                            pbar.update(1)
                            return result
                    
                    # Submit batch of requests
                    tasks = [limited_request(req_id) for req_id in batch_requests]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Control the rate between batches
                    if batch_end < self.total_requests:
                        await asyncio.sleep(delay_between_batches)
            
            total_time = time.time() - start_time
            print(f"\n✅ Load test completed in {total_time:.2f} seconds")
            
        finally:
            await self.session.close()
        
        # Print summary
        self.print_summary()
    
    async def run(self) -> None:
        """Main entry point for the load tester."""
        try:
            self.get_user_input()
            await self.run_load_test()
        except KeyboardInterrupt:
            print("\n\n⏹️  Load test interrupted by user.")
            if self.results:
                print("Partial results:")
                self.print_summary()
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            sys.exit(1)


async def main():
    """Main function to run the API load tester."""
    tester = APILoadTester()
    await tester.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
