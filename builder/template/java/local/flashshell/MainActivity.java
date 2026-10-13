package local.flashshell;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.graphics.Color;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.Collections;

public final class MainActivity extends Activity {
    private WebView web;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getAttributes().layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportZoom(false);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                Log.i("FlashGame", message.message());
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String path = AssetRoute.path(request.getUrl().toString());
                if (path == null) return error(403, "Forbidden");
                try {
                    return new WebResourceResponse(AssetRoute.mime(path), "UTF-8", 200, "OK",
                        Collections.singletonMap("Cache-Control", "no-cache"), getAssets().open(path));
                } catch (IOException e) {
                    Log.e("FlashGame", "Missing asset: " + path);
                    return error(404, "Not Found");
                }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return AssetRoute.path(request.getUrl().toString()) == null;
            }
        });
        setContentView(web);
        fullscreen();
        web.loadUrl(AssetRoute.HOME);
    }
    private static WebResourceResponse error(int code, String reason) {
        return new WebResourceResponse("text/plain", "UTF-8", code, reason,
            Collections.emptyMap(), new ByteArrayInputStream(reason.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) fullscreen();
    }
    private void fullscreen() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
    @Override protected void onPause() {
        web.evaluateJavascript("window.flashPause && window.flashPause()", null);
        web.onPause();
        super.onPause();
    }
    @Override protected void onResume() {
        super.onResume();
        if (web != null) {
            web.onResume();
            web.evaluateJavascript("window.flashResume && window.flashResume()", null);
        }
    }
    @Override public void onBackPressed() {
        new AlertDialog.Builder(this).setMessage("Close “" + getApplicationInfo().loadLabel(getPackageManager()) + "”?")
            .setNegativeButton("Continue", (dialog, which) -> fullscreen())
            .setPositiveButton("Exit", (dialog, which) ->
                web.evaluateJavascript("window.flashSave && window.flashSave()", result -> finish())).show();
    }
    @Override protected void onDestroy() {
        web.destroy();
        super.onDestroy();
    }
}
