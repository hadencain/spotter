"""
Feed source registry. Add new sources here — collector picks them up automatically.
"""
import urllib.parse


def _gnews(query: str) -> dict:
    """Build a Google News RSS entry from a plain-text query. No account or key required."""
    q = urllib.parse.quote_plus(query)
    return {
        "name": f"GNews: {query}",
        "url": f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
    }


RSS_FEEDS = [
    # ── National broadcast ──
    {"name": "NBC News",          "url": "https://feeds.nbcnews.com/nbcnews/public/news"},
    {"name": "CBS News US",       "url": "https://www.cbsnews.com/latest/rss/us"},
    {"name": "Crime Online",      "url": "https://www.crimeonline.com/feed/"},
    {"name": "ABC News",          "url": "https://abcnews.go.com/abcnews/usheadlines"},
    {"name": "Fox News US",       "url": "https://moxie.foxnews.com/google-publisher/us.xml"},
    {"name": "FBI Press",         "url": "https://www.fbi.gov/feeds/fbi_press_releases_rss.xml"},

    # ── Local TV — Southeast ──
    {"name": "11Alive Atlanta",   "url": "https://www.11alive.com/feeds/syndication/rss/news/local/"},
    {"name": "WSVN Miami",        "url": "https://wsvn.com/feed/"},
    {"name": "WFLA Tampa",        "url": "https://www.wfla.com/feed/"},
    {"name": "WRAL Raleigh",      "url": "https://www.wral.com/feeds/syndication/rss/news/local/"},
    {"name": "WSOC Charlotte",    "url": "https://www.wsoctv.com/feeds/syndication/rss/news/local/"},

    # ── Local TV — Northeast ──
    {"name": "6abc Philadelphia", "url": "https://6abc.com/feed/"},
    {"name": "WTAE Pittsburgh",   "url": "https://www.wtae.com/feeds/syndication/rss/news/local/"},
    {"name": "WCVB Boston",       "url": "https://www.wcvb.com/feeds/syndication/rss/news/local/"},

    # ── Local TV — Midwest ──
    {"name": "WLS Chicago",       "url": "https://abc7chicago.com/feed/"},
    {"name": "WKYC Cleveland",    "url": "https://www.wkyc.com/feeds/syndication/rss/news/local/"},
    {"name": "KARE Minneapolis",  "url": "https://www.kare11.com/feeds/syndication/rss/news/local/"},
    {"name": "KSDK St. Louis",    "url": "https://www.ksdk.com/feeds/syndication/rss/news/local/"},

    # ── Local TV — South / Texas ──
    {"name": "WFAA Dallas",       "url": "https://www.wfaa.com/feeds/syndication/rss/news/local/"},
    {"name": "KXAN Austin",       "url": "https://www.kxan.com/feed/"},
    {"name": "KPRC Houston",      "url": "https://www.click2houston.com/feeds/syndication/rss/news/local/"},
    {"name": "WDSU New Orleans",  "url": "https://www.wdsu.com/feeds/syndication/rss/news/local/"},

    # ── Local TV — West ──
    {"name": "KABC Los Angeles",  "url": "https://abc7.com/feed/"},
    {"name": "KGO San Francisco", "url": "https://abc7news.com/feed/"},
    {"name": "KING Seattle",      "url": "https://www.king5.com/feeds/syndication/rss/news/local/"},
    {"name": "KLAS Las Vegas",    "url": "https://www.8newsnow.com/feed/"},
    {"name": "KOIN Portland",     "url": "https://www.koin.com/feed/"},
    {"name": "KNXV Phoenix",      "url": "https://www.abc15.com/feeds/syndication/rss/news/local/"},

    # ── Regional TV & newspapers (verified working or fixed URLs) ──
    # Alabama
    {"name": "WVTM 13 Birmingham",        "url": "https://www.wvtm13.com/topstories-rss"},
    {"name": "WHNT News 19 Huntsville",   "url": "https://whnt.com/feed"},
    # Arizona
    {"name": "Arizona's Family",          "url": "https://www.azfamily.com/feeds/syndication/rss/news/local/"},
    {"name": "FOX 10 Phoenix",            "url": "https://www.fox10phoenix.com/feeds/syndication/rss/news/local/"},
    # Arkansas
    {"name": "KATV Little Rock",          "url": "https://katv.com/feeds/syndication/rss/news/local/"},
    {"name": "THV11 Little Rock",         "url": "https://www.thv11.com/feeds/syndication/rss/news/local/"},
    # California
    {"name": "LA Times",                  "url": "https://www.latimes.com/local/rss2.0.xml"},
    # Colorado
    {"name": "Denver7",                   "url": "https://www.denver7.com/feeds/syndication/rss/news/local/"},
    {"name": "9NEWS Denver",              "url": "https://www.9news.com/feeds/syndication/rss/news/local/"},
    {"name": "Colorado Sun",              "url": "https://coloradosun.com/feed/"},
    # Delaware
    {"name": "WDEL News Wilmington",      "url": "https://www.wdel.com/feed/"},
    # Florida
    {"name": "FOX 35 Orlando",            "url": "https://www.fox35orlando.com/feeds/syndication/rss/news/local/"},
    {"name": "ABC Action News Tampa",     "url": "https://www.abcactionnews.com/feeds/syndication/rss/news/local/"},
    {"name": "News4JAX Jacksonville",     "url": "https://www.news4jax.com/feeds/syndication/rss/news/local/"},
    {"name": "Local 10 Miami",            "url": "https://www.local10.com/feeds/syndication/rss/news/local/"},
    {"name": "CBS12 West Palm Beach",     "url": "https://cbs12.com/feeds/syndication/rss/news/local/"},
    {"name": "NBC 6 South Florida",       "url": "https://www.nbcmiami.com/feeds/syndication/rss/news/local/"},
    {"name": "WPTV West Palm Beach",      "url": "https://www.wptv.com/feeds/syndication/rss/news/local/"},
    # Georgia
    {"name": "FOX 5 Atlanta",             "url": "https://www.fox5atlanta.com/feeds/syndication/rss/news/local/"},
    {"name": "WSB-TV Atlanta",            "url": "https://www.wsbtv.com/feeds/syndication/rss/news/local/"},
    {"name": "WMAZ Macon",                "url": "https://www.13wmaz.com/feeds/syndication/rss/news/local/"},
    {"name": "WTOC Savannah",             "url": "https://www.wtoc.com/feeds/syndication/rss/news/local/"},
    # Hawaii
    {"name": "Hawaii News Now",           "url": "https://www.hawaiinewsnow.com/feeds/syndication/rss/news/local/"},
    {"name": "KHON2 Honolulu",            "url": "https://www.khon2.com/feed/"},
    # Idaho
    {"name": "Idaho News 6",              "url": "https://www.kivitv.com/feeds/syndication/rss/news/local/"},
    # Illinois
    {"name": "FOX 32 Chicago",            "url": "https://www.fox32chicago.com/feeds/syndication/rss/news/local/"},
    {"name": "WGN News Chicago",          "url": "https://wgntv.com/feed/"},
    {"name": "Chicago Sun-Times",         "url": "https://chicago.suntimes.com/feed"},
    # Indiana
    {"name": "FOX59 Indianapolis",        "url": "https://www.fox59.com/feed"},
    {"name": "WRTV Indianapolis",         "url": "https://www.wrtv.com/feeds/syndication/rss/news/local/"},
    {"name": "WISH-TV Indianapolis",      "url": "https://www.wishtv.com/feed"},
    # Louisiana
    {"name": "Times-Picayune New Orleans","url": "https://www.nola.com/search/?f=rss"},
    {"name": "The Advocate Baton Rouge",  "url": "https://www.theadvocate.com/search/?f=rss"},
    {"name": "WBRZ-TV Baton Rouge",       "url": "https://www.wbrz.com/rss-feeds/"},
    {"name": "WAFB 9 Baton Rouge",        "url": "https://www.wafb.com/feeds/syndication/rss/news/local/"},
    {"name": "KATC Lafayette",            "url": "https://www.katc.com/feeds/syndication/rss/news/local/"},
    # Maryland
    {"name": "WTOP Washington DC",        "url": "https://wtop.com/feed"},
    {"name": "WBAL-TV 11 Baltimore",      "url": "https://www.wbal.com/feed"},
    # Mississippi
    {"name": "Mississippi Today",         "url": "https://mississippitoday.org/feed"},
    # Missouri
    {"name": "St. Louis Post-Dispatch",   "url": "https://www.stltoday.com/search/?f=rss"},
    {"name": "Missouri Independent",      "url": "https://www.moindependent.com/feed"},
    # Nebraska
    {"name": "Lincoln Journal Star",      "url": "https://www.lincolnjournalstar.com/search/?f=rss"},
    # Nevada
    {"name": "The Nevada Independent",    "url": "https://thenevadaindependent.com/feed"},
    # New Jersey
    {"name": "NJ Spotlight News",         "url": "https://www.njspotlightnews.org/feed"},
    {"name": "New Jersey Monitor",        "url": "https://newjerseymonitor.com/feed"},
    # New Mexico
    {"name": "Santa Fe New Mexican",      "url": "https://www.santafenewmexican.com/search/?f=rss"},
    # New York
    {"name": "Gothamist NYC",             "url": "https://gothamist.com/feed"},
    # Oklahoma
    {"name": "Oklahoma Watch",            "url": "https://oklahomawatch.org/feed"},
    # Oregon
    {"name": "KATU ABC 2 Portland",       "url": "https://www.katu.com/feeds/syndication/rss/news/local/"},
    # Pennsylvania
    {"name": "Fox 29 Philadelphia",       "url": "https://www.fox29.com/feeds/syndication/rss/news/local/"},
    # South Carolina
    {"name": "WBTW Florence SC",          "url": "https://www.wbtw.com/feeds/syndication/rss/news/local/"},
    # Texas
    {"name": "Texas Tribune",             "url": "https://www.texastribune.org/feed"},
    {"name": "KTRK ABC13 Houston",        "url": "https://www.abc13.com/feeds/syndication/rss/news/local/"},
    {"name": "NBC DFW Dallas",            "url": "https://www.nbcdfw.com/feeds/syndication/rss/news/local/"},
    {"name": "FOX 4 Dallas",              "url": "https://www.fox4news.com/feeds/syndication/rss/news/local/"},
    {"name": "KVIA ABC7 El Paso",         "url": "https://www.kvia.com/feeds/syndication/rss/news/local/"},
    # Utah
    {"name": "KSL 5 Utah",               "url": "https://www.ksl.com/feeds/syndication/rss/news/local/"},
    {"name": "Fox 13 Utah",              "url": "https://www.fox13utah.com/feeds/syndication/rss/news/local/"},
    # Virginia
    {"name": "Virginia Mercury",          "url": "https://www.virginiamercury.com/feed"},
    # Wyoming
    {"name": "Cowboy State Daily",        "url": "https://cowboystatedaily.com/feed"},

    # ── Mall & retail violence ──
    _gnews("mall shooting"),
    _gnews("mall stabbing"),
    _gnews("mall robbery"),
    _gnews("mall fight brawl"),
    _gnews("mall threat evacuate"),
    _gnews("mall arrest"),
    _gnews("mall attack"),
    _gnews("mall lockdown"),
    _gnews("shopping center shooting"),
    _gnews("shopping center robbery"),
    _gnews("shopping center fight"),
    _gnews("outlet mall crime"),
    _gnews("strip mall shooting"),
    _gnews("department store robbery"),
    _gnews("big box store shooting"),

    # ── Retail crime ──
    _gnews("retail theft arrest"),
    _gnews("shoplifting organized retail crime"),
    _gnews("smash and grab robbery"),
    _gnews("flash mob robbery store"),
    _gnews("retail worker assault"),
    _gnews("loss prevention shooting"),
    _gnews("ORC organized retail crime"),
    _gnews("shoplifting gang arrested"),

    # ── Parking lot / exterior ──
    _gnews("parking lot shooting mall"),
    _gnews("parking garage robbery"),
    _gnews("carjacking mall parking"),
    _gnews("parking lot assault robbery"),

    # ── Active threat / mass casualty ──
    _gnews("active shooter public place"),
    _gnews("mass shooting public"),
    _gnews("bomb threat building evacuate"),
    _gnews("hostage situation store"),
    _gnews("stabbing spree public"),

    # ── Child safety / predators ──
    _gnews("child abduction mall store"),
    _gnews("amber alert"),
    _gnews("child luring retail"),
    _gnews("sex offender mall arrest"),
    _gnews("child found abandoned mall"),

    # ── Gang / group activity ──
    _gnews("gang fight public shooting"),
    _gnews("juvenile crime mall arrest"),
    _gnews("group assault robbery"),
    _gnews("flash mob violence"),
    _gnews("teen mob store brawl"),
]
