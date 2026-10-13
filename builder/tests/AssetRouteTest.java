package local.flashshell;

public final class AssetRouteTest {
    public static void main(String[] args) {
        check("game/main.swf".equals(AssetRoute.path("https://appassets.androidplatform.net/assets/game/main.swf?x=1")), "main SWF");
        check("game/\u0418\u0433\u0440\u0430 \u0441 \u043f\u0440\u043e\u0431\u0435\u043b\u043e\u043c/\u0441\u0442\u0430\u0440\u0442.swf".equals(AssetRoute.path("https://appassets.androidplatform.net/assets/game/%D0%98%D0%B3%D1%80%D0%B0%20%D1%81%20%D0%BF%D1%80%D0%BE%D0%B1%D0%B5%D0%BB%D0%BE%D0%BC/%D1%81%D1%82%D0%B0%D1%80%D1%82.swf")), "UTF-8 and spaces");
        check("game/a+b.swf".equals(AssetRoute.path("https://appassets.androidplatform.net/assets/game/a+b.swf")), "literal plus");
        check("game/a%b.swf".equals(AssetRoute.path("https://appassets.androidplatform.net/assets/game/a%25b.swf")), "literal percent decoded once");
        check("game/a#b?.swf".equals(AssetRoute.path("https://appassets.androidplatform.net/assets/game/a%23b%3F.swf")), "encoded URL punctuation");
        for (String suffix : new String[]{"../secret", "%2e%2e/secret", "a%2fb.swf", "a%5cb.swf", "a%00b.swf", "a%GGb.swf"}) {
            check(AssetRoute.path("https://appassets.androidplatform.net/assets/" + suffix) == null, "invalid path " + suffix);
        }
        for (String url : new String[]{"https://example.com/assets/game/main.swf", "http://appassets.androidplatform.net/assets/game/main.swf", "https://appassets.androidplatform.net.evil/assets/game/main.swf"}) {
            check(AssetRoute.path(url) == null, "external URL");
        }
        check("application/wasm".equals(AssetRoute.mime("core.wasm")), "WASM MIME");
        check("application/x-shockwave-flash".equals(AssetRoute.mime("scene.swf")), "SWF MIME");
        System.out.println("Asset routes: ordinary, UTF-8, punctuation and blocked paths passed");
    }
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
}
