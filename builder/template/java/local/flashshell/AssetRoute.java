package local.flashshell;

import java.net.URI;
import java.net.URLDecoder;
import java.util.Locale;

/** Local HTTPS origin, decoded one segment at a time to forbid traversal. */
public final class AssetRoute {
    public static final String HOME = "https://appassets.androidplatform.net/assets/player/index.html";
    public static String path(String url) {
        try {
            URI uri = new URI(url);
            if (!"https".equals(uri.getScheme()) || !"appassets.androidplatform.net".equals(uri.getHost())
                    || uri.getPort() != -1 || uri.getUserInfo() != null) return null;
            String raw = uri.getRawPath();
            if (raw == null || !raw.startsWith("/assets/")) return null;
            StringBuilder path = new StringBuilder();
            for (String segment : raw.substring(8).split("/", -1)) {
                String decoded = URLDecoder.decode(segment.replace("+", "%2B"), "UTF-8");
                if (decoded.isEmpty() || decoded.equals(".") || decoded.equals("..")
                        || decoded.contains("/") || decoded.contains("\\") || decoded.contains("\uFFFD")) return null;
                for (int i = 0; i < decoded.length(); i++) {
                    if (decoded.charAt(i) < 32) return null;
                }
                if (path.length() != 0) path.append('/');
                path.append(decoded);
            }
            return path.toString();
        } catch (Exception ignored) { return null; }
    }
    public static String mime(String path) {
        String name = path.toLowerCase(Locale.ROOT);
        if (name.endsWith(".wasm")) return "application/wasm";
        if (name.endsWith(".js")) return "application/javascript";
        if (name.endsWith(".html") || name.endsWith(".htm")) return "text/html";
        if (name.endsWith(".css")) return "text/css";
        if (name.endsWith(".swf")) return "application/x-shockwave-flash";
        if (name.endsWith(".png")) return "image/png";
        if (name.endsWith(".gif")) return "image/gif";
        if (name.endsWith(".jpg") || name.endsWith(".jpeg")) return "image/jpeg";
        if (name.endsWith(".svg")) return "image/svg+xml";
        if (name.endsWith(".json")) return "application/json";
        if (name.endsWith(".xml")) return "application/xml";
        if (name.endsWith(".txt")) return "text/plain";
        if (name.endsWith(".mp3")) return "audio/mpeg";
        if (name.endsWith(".wav")) return "audio/wav";
        if (name.endsWith(".ogg")) return "audio/ogg";
        return "application/octet-stream";
    }
}
