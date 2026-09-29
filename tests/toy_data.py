"""A tiny synthetic retrieval set used only for offline tests."""

SNIPPETS = {
    "dijkstra": "import heapq\n\ndef shortest_paths(graph, src):\n    dist = {src: 0}\n    heap = [(0, src)]\n    while heap:\n        d, u = heapq.heappop(heap)\n        for v, w in graph[u]:\n            nd = d + w\n            if nd < dist.get(v, 10**18):\n                dist[v] = nd\n                heapq.heappush(heap, (nd, v))\n    return dist\n",
    "bfs_grid": "from collections import deque\n\ndef bfs(grid, start):\n    n, m = len(grid), len(grid[0])\n    visited = [[False] * m for _ in range(n)]\n    q = deque([start])\n    visited[start[0]][start[1]] = True\n    while q:\n        x, y = q.popleft()\n        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):\n            nx, ny = x + dx, y + dy\n            if 0 <= nx < n and 0 <= ny < m and not visited[nx][ny]:\n                visited[nx][ny] = True\n                q.append((nx, ny))\n",
    "gcd_lcm": "from math import gcd\n\nt = int(input())\nfor _ in range(t):\n    a, b = map(int, input().split())\n    g = gcd(a, b)\n    print(a // g * b)\n",
    "palindrome": "s = input()\nprint('YES' if s == s[::-1] else 'NO')\n",
    "knapsack": "n, W = map(int, input().split())\nitems = [tuple(map(int, input().split())) for _ in range(n)]\ndp = [0] * (W + 1)\nfor w, v in items:\n    for c in range(W, w - 1, -1):\n        dp[c] = max(dp[c], dp[c - w] + v)\nprint(dp[W])\n",
    "sort_pairs": "n = int(input())\na = sorted(map(int, input().split()))\nprint(sum(a[i] * (i + 1) for i in range(n)))\n",
    "bit_xor": "n = int(input())\na = list(map(int, input().split()))\nr = 0\nfor x in a:\n    r ^= x\nprint(r)\n",
    "prime_sieve": "n = int(input())\nsieve = [True] * (n + 1)\nsieve[0] = sieve[1] = False\nfor i in range(2, int(n ** 0.5) + 1):\n    if sieve[i]:\n        for j in range(i * i, n + 1, i):\n            sieve[j] = False\nprint(sum(sieve))\n",
    "binary_search": "from bisect import bisect_left\n\ndef first_at_least(a, x):\n    i = bisect_left(a, x)\n    return i if i < len(a) else -1\n",
    "geometry": "import math\n\nx1, y1, x2, y2 = map(int, input().split())\nprint(math.hypot(x2 - x1, y2 - y1))\n",
}

QUERIES = {
    "q_dijkstra": ("Find the length of the shortest path from city 1 to every other city in a weighted road graph.", "dijkstra"),
    "q_bfs": ("A robot moves on a grid of cells. Find all cells the robot can reach from its starting cell without crossing walls.", "bfs_grid"),
    "q_gcd": ("For each test case print the least common multiple of two integers a and b.", "gcd_lcm"),
    "q_pal": ("Given a string, determine whether it reads the same forwards and backwards. Print YES or NO.", "palindrome"),
    "q_knap": ("There are n items with weights and values and a bag of capacity W. Maximize the total value you can carry.", "knapsack"),
    "q_xor": ("Compute the bitwise XOR of all the numbers in the array.", "bit_xor"),
    "q_prime": ("Count how many prime numbers are there not greater than n.", "prime_sieve"),
    "q_dist": ("Given the coordinates of two points on a plane, print the distance between them.", "geometry"),
}
