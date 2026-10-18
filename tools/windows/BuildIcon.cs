// Native vector rendering of assets/app-icon.svg; no image service or external tools required.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Collections.Generic;

class BuildIcon {
    static GraphicsPath Shape(Action<GraphicsPath> draw) { var p = new GraphicsPath(); draw(p); return p; }
    static Bitmap Render(int size) {
        var bitmap = new Bitmap(size, size, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bitmap)) {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.ScaleTransform(size / 256f, size / 256f);
            using (var dark = new SolidBrush(Color.FromArgb(33,31,26)))
            using (var gold = new SolidBrush(Color.FromArgb(211,179,108)))
            using (var cream = new SolidBrush(Color.FromArgb(245,237,218)))
            using (var green = new SolidBrush(Color.FromArgb(146,168,112))) {
                using (var box = Shape(p => { p.AddArc(8,8,108,108,180,90); p.AddArc(140,8,108,108,270,90); p.AddArc(140,140,108,108,0,90); p.AddArc(8,140,108,108,90,90); p.CloseFigure(); })) g.FillPath(dark,box);
                using (var book = Shape(p => { p.StartFigure(); p.AddBezier(49,99,74,89,101,92,128,108); p.AddBezier(128,108,155,92,182,89,207,99); p.AddLine(207,99,207,194); p.AddBezier(207,194,180,185,153,189,128,206); p.AddBezier(128,206,103,189,76,185,49,194); p.CloseFigure(); })) g.FillPath(gold,book);
                using (var spine = new Pen(Color.FromArgb(119,97,56),7)) { spine.StartCap=spine.EndCap=LineCap.Round; g.DrawLine(spine,128,111,128,189); }
                if (size >= 32) using (var ink = new Pen(Color.FromArgb(116,33,31,26),7)) {
                    ink.StartCap=ink.EndCap=LineCap.Round;
                    g.DrawBezier(ink,68,121,83,118,97,119,108,126); g.DrawBezier(ink,68,143,83,140,97,141,108,148);
                    g.DrawBezier(ink,148,126,164,119,178,118,189,121); g.DrawBezier(ink,148,148,164,141,178,140,189,143);
                }
                using (var cloud = Shape(p => { p.StartFigure(); p.AddBezier(106,76,85,76,83,48,102,44); p.AddBezier(102,44,108,19,144,21,151,42); p.AddBezier(151,42,174,38,185,76,160,76); p.CloseFigure(); })) g.FillPath(cream,cloud);
                g.FillEllipse(dark,179,177,44,44); g.FillEllipse(green,187,185,28,28);
            }
        }
        return bitmap;
    }
    static void Main(string[] args) {
        Directory.CreateDirectory(args[0]);
        var images = new List<byte[]>();
        int[] sizes = {16,24,32,48,64,128,256};
        foreach (int size in sizes) using (var bitmap = Render(size)) using (var memory = new MemoryStream()) {
            bitmap.Save(memory,ImageFormat.Png); images.Add(memory.ToArray());
            if (size == 256) bitmap.Save(Path.Combine(args[0],"app-icon.png"),ImageFormat.Png);
        }
        using (var file=File.Create(Path.Combine(args[0],"app-icon.ico"))) using (var writer=new BinaryWriter(file)) {
            writer.Write((ushort)0); writer.Write((ushort)1); writer.Write((ushort)sizes.Length);
            int offset=6+16*sizes.Length;
            for (int i=0;i<sizes.Length;i++) {
                writer.Write((byte)(sizes[i]==256?0:sizes[i])); writer.Write((byte)(sizes[i]==256?0:sizes[i]));
                writer.Write((byte)0); writer.Write((byte)0); writer.Write((ushort)1); writer.Write((ushort)32);
                writer.Write(images[i].Length); writer.Write(offset); offset+=images[i].Length;
            }
            foreach (var image in images) writer.Write(image);
        }
    }
}
