'''
 *  Project             :   KJScreener
 *  Author              :   Khushal Jain
 *  Created             :   02/05/2026
 *  Description         :   Class for maintaining changelog
'''

from classes.ColorText import colorText

VERSION = "3.1.0"

changelog = colorText.BOLD + '[ChangeLog]\n' + colorText.END + colorText.BLUE + '''
[3.1.0]
1. New LedgerLens tab - pull complete company fundamentals (quarterly results, P&L, balance sheet, cash flow, ratios, shareholding, peers, pros/cons, documents) straight from screener.in.
2. Removed the yfinance-based Live Quote tab (replaced by LedgerLens).
3. Fixed symbol-resolution bug in company search for large-cap stocks.

[3.0.2]
1. Fixed _load_real_agents() import dance - removed fragile site.getsitepackages() hack, use direct sys.path manipulation.
2. Fixed OtaUpdater crash with semver versions like "3.0.1" (float() ValueError).
3. Fixed Styler.applymap deprecation warning → Styler.map.
4. Fixed use_container_width deprecation warning → width parameter.
5. Fixed ai_provider/ai_remember_key Session State API conflict (removed redundant default value params).
''' + colorText.END
