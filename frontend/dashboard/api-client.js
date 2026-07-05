(function () {
  const DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
  const API_BASE_STORAGE_KEY = "minerva_api_base_url";
  const API_KEY_STORAGE_KEY = "minerva_api_key";
  let currentBaseUrl = "";
  let currentApiKey = "";
  let probePromise = null;

  function normalizeApiBaseUrl(value) {
    const text = String(value || "").trim().replace(/\/+$/, "");
    if (!text || !/^https?:\/\//i.test(text)) return "";
    return text;
  }

  function apiBaseFromQuery() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return normalizeApiBaseUrl(params.get("apiBase") || params.get("api_base"));
    } catch {
      return "";
    }
  }

  function apiBaseFromStorage() {
    try {
      return normalizeApiBaseUrl(window.localStorage?.getItem(API_BASE_STORAGE_KEY));
    } catch {
      return "";
    }
  }

  function apiKeyFromQuery() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return String(params.get("apiKey") || params.get("api_key") || "").trim();
    } catch {
      return "";
    }
  }

  function apiKeyFromStorage() {
    try {
      return String(window.localStorage?.getItem(API_KEY_STORAGE_KEY) || "").trim();
    } catch {
      return "";
    }
  }

  function sameOriginApiBase() {
    if (!/^https?:$/i.test(window.location.protocol)) return "";
    const path = window.location.pathname || "";
    const backendServedDashboard = path.startsWith("/dashboard-ui") || path.startsWith("/dashboard-assets");
    const backendLikePort = ["8000", "8001", "8002"].includes(window.location.port || "");
    return backendServedDashboard || backendLikePort ? normalizeApiBaseUrl(window.location.origin) : "";
  }

  function unique(values) {
    const seen = new Set();
    return values.map(normalizeApiBaseUrl).filter(Boolean).filter((value) => {
      if (seen.has(value)) return false;
      seen.add(value);
      return true;
    });
  }

  function apiBaseCandidates() {
    return unique([
      window.MINERVA_API_BASE_URL,
      apiBaseFromQuery(),
      apiBaseFromStorage(),
      sameOriginApiBase(),
      DEFAULT_LOCAL_API_BASE_URL,
      "http://localhost:8000",
      "http://127.0.0.1:8001",
      "http://localhost:8001",
    ]);
  }

  function setApiBaseUrl(value, options = {}) {
    const normalized = normalizeApiBaseUrl(value);
    if (!normalized) return getBaseUrl();
    currentBaseUrl = normalized;
    window.MINERVA_CURRENT_API_BASE_URL = normalized;
    if (options.persist) {
      try {
        window.localStorage?.setItem(API_BASE_STORAGE_KEY, normalized);
      } catch {
        // Ignore storage failures in private browsing / file contexts.
      }
    }
    return currentBaseUrl;
  }

  function getBaseUrl() {
    if (!currentBaseUrl) {
      currentBaseUrl = apiBaseCandidates()[0] || DEFAULT_LOCAL_API_BASE_URL;
    }
    return currentBaseUrl;
  }

  function apiUrl(path) {
    if (/^https?:\/\//i.test(String(path || ""))) return path;
    return `${getBaseUrl()}${String(path || "").startsWith("/") ? path : `/${path}`}`;
  }

  function setApiKey(value, options = {}) {
    currentApiKey = String(value || "").trim();
    if (options.persist) {
      try {
        if (currentApiKey) window.localStorage?.setItem(API_KEY_STORAGE_KEY, currentApiKey);
        else window.localStorage?.removeItem(API_KEY_STORAGE_KEY);
      } catch {
        // Ignore storage failures.
      }
    }
    return currentApiKey;
  }

  function getApiKey() {
    if (!currentApiKey) {
      currentApiKey = String(window.MINERVA_API_KEY || apiKeyFromQuery() || apiKeyFromStorage() || "").trim();
      if (apiKeyFromQuery()) {
        setApiKey(currentApiKey, { persist: true });
      }
    }
    return currentApiKey;
  }

  function authHeaders() {
    const key = getApiKey();
    return key ? { "X-API-Key": key } : {};
  }

  function apiUrlWithAuth(path) {
    const url = new URL(apiUrl(path), window.location.href);
    const key = getApiKey();
    if (key) url.searchParams.set("api_key", key);
    return url.toString();
  }

  async function probeApiBase(baseUrl, timeoutMs) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${baseUrl}/api/health`, {
        cache: "no-store",
        headers: { Accept: "application/json", ...authHeaders() },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Health check returned ${response.status}`);
      return await response.json();
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  async function ensureApiBaseReachable(options = {}) {
    const timeoutMs = Number(options.timeoutMs || 2500);
    if (probePromise && !options.force) return probePromise;
    probePromise = (async () => {
      let lastError = null;
      const candidates = apiBaseCandidates();
      for (const candidate of candidates) {
        try {
          const payload = await probeApiBase(candidate, timeoutMs);
          setApiBaseUrl(candidate, { persist: Boolean(apiBaseFromQuery() || window.MINERVA_API_BASE_URL) });
          return payload;
        } catch (error) {
          lastError = error;
        }
      }
      const error = new Error(
        `Backend is not connected. Tried ${candidates.join(", ")}. Start FastAPI at http://127.0.0.1:8000.`
      );
      error.status = 0;
      error.cause = lastError;
      throw error;
    })();
    try {
      return await probePromise;
    } finally {
      probePromise = null;
    }
  }

  window.MinervaApi = {
    apiUrl,
    apiUrlWithAuth,
    ensureApiBaseReachable,
    getBaseUrl,
    setApiBaseUrl,
    getApiKey,
    setApiKey,
    authHeaders,
    apiBaseCandidates,
  };
})();
