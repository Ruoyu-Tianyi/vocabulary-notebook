// Built using the .NET Framework compiler included with Windows; no extra desktop runtime.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace VocabularyDesktop {
    public sealed class LocalService {
        public readonly string Root;
        public readonly string Identity;
        public readonly string Url;
        public readonly string Runtime;
        readonly int port;
        readonly JavaScriptSerializer json = new JavaScriptSerializer();

        public LocalService(string root, int servicePort) {
            Root = Path.GetFullPath(root).TrimEnd('\\', '/');
            port = servicePort;
            Url = "http://127.0.0.1:" + port + "/";
            Runtime = Path.Combine(Root, ".runtime");
            using (var sha = SHA256.Create())
                Identity = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(Root.Replace('\\', '/').ToLowerInvariant()))).Replace("-", "").ToLowerInvariant();
        }

        public bool Ready() {
            try {
                var request = (HttpWebRequest)WebRequest.Create(Url + "api/instance");
                request.Proxy = null;
                request.Timeout = request.ReadWriteTimeout = 800;
                using (var response = request.GetResponse())
                using (var reader = new StreamReader(response.GetResponseStream())) {
                    var info = json.Deserialize<Dictionary<string, object>>(reader.ReadToEnd());
                    return (string)info["application"] == "drive-vocabulary-book" && (string)info["installation_id"] == Identity;
                }
            } catch { return false; }
        }

        bool PortBusy() {
            try {
                using (var socket = new TcpClient()) {
                    var pending = socket.BeginConnect("127.0.0.1", port, null, null);
                    try { return pending.AsyncWaitHandle.WaitOne(500) && socket.Connected; }
                    finally { pending.AsyncWaitHandle.Close(); }
                }
            } catch { return false; }
        }

        public void Start() {
            if (Ready()) return;
            if (PortBusy()) throw new Exception("启动位置已被其他程序或另一份词汇本占用。请先关闭原来的启动窗口，再重试。");
            string python = Path.Combine(Root, @".venv\Scripts\python.exe");
            if (!File.Exists(python)) throw new Exception("词汇本尚未完成安装。请让安装 Agent 按 README 完成安装后重试。");
            foreach (string file in new [] { "app.py", "desktop_service.py", @"frontend\dist\index.html" })
                if (!File.Exists(Path.Combine(Root, file))) throw new Exception("程序文件不完整，请让安装 Agent 更新当前安装目录后重试。");
            Directory.CreateDirectory(Runtime);
            string stop = Path.Combine(Runtime, "stop-" + Guid.NewGuid().ToString("N") + ".request");
            var info = new ProcessStartInfo(python, "\"" + Path.Combine(Root, "desktop_service.py") + "\" --stop-file \"" + stop + "\" --port " + port);
            info.WorkingDirectory = Root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            using (var process = Process.Start(info)) {
                for (int i = 0; i < 120; i++) {
                    if (Ready()) return;
                    if (process.HasExited) throw new Exception("词汇本启动失败，请查看本机日志，或交给安装 Agent 检查。");
                    Thread.Sleep(250);
                }
            }
            throw new Exception("启动时间较长，服务仍可能正在准备。请稍后再次双击；如一直无法打开，请查看日志。");
        }

        public string StopPath() {
            try {
                var info = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(Runtime, "desktop-service.json"), Encoding.UTF8));
                if ((string)info["installation_id"] != Identity) return null;
                string stop = Path.GetFullPath((string)info["stop_file"]);
                string name = Path.GetFileName(stop);
                if (!String.Equals(Path.GetDirectoryName(stop), Runtime, StringComparison.OrdinalIgnoreCase)
                    || !name.StartsWith("stop-", StringComparison.Ordinal) || !name.EndsWith(".request", StringComparison.Ordinal)) return null;
                using (var process = Process.GetProcessById(Convert.ToInt32(info["pid"])))
                    if (process.HasExited) return null;
                return stop;
            } catch { return null; }
        }

        public void Stop() {
            string stop = StopPath();
            if (stop == null) {
                if (Ready()) throw new Exception("词汇本由原来的启动窗口运行。请关闭那个窗口；当前启动器不会强行结束其他程序。");
                if (PortBusy()) throw new Exception("此位置运行的不是当前目录的词汇本，未停止任何程序。");
                return;
            }
            File.WriteAllText(stop, "stop", Encoding.UTF8);
            string metadata = Path.Combine(Runtime, "desktop-service.json");
            // Wait for the full lifespan/Drive shutdown, not merely the HTTP socket closing.
            for (int i = 0; i < 180; i++) {
                if (!File.Exists(metadata) && !PortBusy()) return;
                Thread.Sleep(250);
            }
            throw new Exception("正在等待同步任务安全结束，请稍后再试。没有强制结束进程。");
        }

        public void Open() { Process.Start(new ProcessStartInfo(Url) { UseShellExecute = true }); }
    }

    sealed class TrayApplication : ApplicationContext {
        readonly LocalService service;
        readonly NotifyIcon tray;
        readonly ToolStripMenuItem stop;
        readonly Form splash;
        readonly System.Windows.Forms.Timer timer;
        bool stopping;
        bool started;

        public TrayApplication(LocalService local) {
            service = local;
            tray = new NotifyIcon { Text = "云端词汇本", Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath), Visible = true };
            var menu = new ContextMenuStrip();
            menu.Items.Add("打开词汇本", null, (s, e) => Open());
            stop = new ToolStripMenuItem("安全停止词汇本并退出", null, async (s, e) => await Stop());
            menu.Items.Add(stop);
            menu.Items.Add("查看启动日志", null, (s, e) => ShowLog());
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("仅退出启动器（服务继续运行）", null, (s, e) => ExitThread());
            tray.ContextMenuStrip = menu;
            tray.DoubleClick += (s, e) => Open();
            splash = new Form { Text = "云端词汇本", ClientSize = new Size(350, 120), FormBorderStyle = FormBorderStyle.FixedDialog,
                StartPosition = FormStartPosition.CenterScreen, MaximizeBox = false, MinimizeBox = false,
                ControlBox = false, BackColor = Color.FromArgb(29, 28, 24), Icon = tray.Icon };
            splash.Controls.Add(new Label { Text = "正在打开你的词汇本…", Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
                ForeColor = Color.FromArgb(218, 187, 111), Font = new Font("Microsoft YaHei UI", 12) });
            splash.Shown += async (s, e) => {
                try { await Task.Run(() => service.Start()); started = true; splash.Close(); service.Open(); }
                catch (Exception error) { splash.Close(); Error(error); ExitThread(); }
            };
            timer = new System.Windows.Forms.Timer { Interval = 2000 };
            timer.Tick += (s, e) => {
                if (!stopping) {
                    stop.Enabled = service.StopPath() != null;
                    if (started && !stop.Enabled && !service.Ready()) ExitThread();
                }
            };
            timer.Start();
            splash.Show();
        }

        void Open() { if (service.Ready()) service.Open(); else Error(new Exception("服务尚未就绪，请稍后重试。")); }
        async Task Stop() {
            if (stopping) return;
            stopping = true;
            stop.Enabled = false;
            tray.Text = "云端词汇本 · 正在安全停止";
            try { await Task.Run(() => service.Stop()); ExitThread(); }
            catch (Exception error) { Error(error); stopping = false; tray.Text = "云端词汇本"; }
        }
        void ShowLog() {
            string log = Path.Combine(service.Runtime, "service.log");
            if (File.Exists(log)) Process.Start(new ProcessStartInfo(log) { UseShellExecute = true });
            else MessageBox.Show("尚无启动日志。", "云端词汇本");
        }
        void Error(Exception error) { MessageBox.Show(error.Message + "\n\n启动日志：" + Path.Combine(service.Runtime, "service.log"), "云端词汇本", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        protected override void ExitThreadCore() { timer.Stop(); timer.Dispose(); tray.Visible = false; tray.Dispose(); base.ExitThreadCore(); }
    }

    static class Program {
        [STAThread]
        static int Main(string[] args) {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            int port = 1400;
            // CLI controls are for safe updates/verification; normal desktop use needs no arguments.
            int configured;
            if (Int32.TryParse(Environment.GetEnvironmentVariable("VOCAB_LAUNCHER_PORT"), out configured) && configured > 1024 && configured < 65536) port = configured;
            var service = new LocalService(root, port);
            bool cli = args.Length > 0;
            try {
                if (cli && args[0] == "--stop") {
                    service.Stop();
                    // Give a tray instance time to observe service exit and release its mutex.
                    for (int i = 0; i < 100; i++) {
                        Mutex existing;
                        if (!Mutex.TryOpenExisting(@"Local\DriveVocabularyBook-" + service.Identity, out existing)) break;
                        existing.Dispose();
                        if (i == 99) throw new Exception("启动器仍在关闭，请稍后重试更新。");
                        Thread.Sleep(100);
                    }
                    return 0;
                }
                if (cli && args[0] == "--check") return service.Ready() ? 0 : 1;
                bool created;
                using (var mutex = new Mutex(true, @"Local\DriveVocabularyBook-" + service.Identity, out created)) {
                    if (!created) { if (!cli && service.Ready()) service.Open(); return cli && !service.Ready() ? 1 : 0; }
                    if (cli && args[0] == "--start") { service.Start(); return 0; }
                    Application.EnableVisualStyles();
                    Application.SetCompatibleTextRenderingDefault(false);
                    Application.Run(new TrayApplication(service));
                }
                return 0;
            } catch (Exception error) {
                if (!cli) MessageBox.Show(error.Message, "云端词汇本", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }
    }
}
