(function () {
  const refreshSeconds = Number(window.LOOKING_GLASS_REFRESH_SECONDS || 0);
  if (!refreshSeconds || refreshSeconds < 1) {
    return;
  }

  window.setTimeout(function () {
    const url = new URL(window.location.href);
    url.searchParams.set("_ts", Date.now().toString());
    window.location.replace(url.toString());
  }, refreshSeconds * 1000);
})();
