using System;
using System.Globalization;
using System.IO;
using System.Threading;
using System.Windows.Media;
using System.Windows.Threading;

internal sealed class AudioClock
{
    private readonly MediaPlayer player = new MediaPlayer();
    private readonly Dispatcher dispatcher = Dispatcher.CurrentDispatcher;
    private readonly DispatcherTimer timer = new DispatcherTimer();
    private double duration;
    private bool playing;
    private bool ended;

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        var clock = new AudioClock();
        try
        {
            clock.Run(Path.GetFullPath(args[0]));
            return Environment.ExitCode;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.Message);
            return 1;
        }
        finally
        {
            clock.timer.Stop();
            clock.player.Close();
        }
    }

    private void Run(string path)
    {
        player.MediaOpened += (sender, args) =>
        {
            if (!player.NaturalDuration.HasTimeSpan)
            {
                Fail("The audio duration is unavailable.");
                return;
            }
            duration = player.NaturalDuration.TimeSpan.TotalSeconds;
            Publish();
            timer.Start();
            new Thread(ReadCommands) { IsBackground = true }.Start();
        };
        player.MediaFailed += (sender, args) => Fail(args.ErrorException.Message);
        player.MediaEnded += (sender, args) =>
        {
            playing = false;
            ended = true;
            Publish();
        };
        timer.Interval = TimeSpan.FromMilliseconds(20);
        timer.Tick += (sender, args) => Publish();
        player.Open(new UriBuilder { Scheme = Uri.UriSchemeFile, Host = "", Path = path.Replace("%", "%25") }.Uri);
        Dispatcher.Run();
    }

    private void Fail(string error)
    {
        Console.Error.WriteLine(error);
        Environment.ExitCode = 1;
        dispatcher.BeginInvokeShutdown(DispatcherPriority.Send);
    }

    private void Publish()
    {
        double position = ended ? duration : Math.Min(duration, Math.Max(0, player.Position.TotalSeconds));
        Console.WriteLine("{0:F6}\t{1:F6}\t{2}\t{3}", position, duration, playing ? 1 : 0, ended ? 1 : 0);
    }

    private void ReadCommands()
    {
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            var command = line.Split(' ');
            dispatcher.BeginInvoke(DispatcherPriority.Normal, new Action(() => Execute(command)));
            if (command[0] == "quit") return;
        }
        dispatcher.BeginInvokeShutdown(DispatcherPriority.Normal);
    }

    private void Execute(string[] command)
    {
        switch (command[0])
        {
            case "play":
                if (ended) player.Position = TimeSpan.Zero;
                ended = false;
                player.Play();
                playing = true;
                break;
            case "pause":
                player.Pause();
                playing = false;
                break;
            case "seek":
                double seconds = double.Parse(command[1], CultureInfo.InvariantCulture);
                player.Position = TimeSpan.FromSeconds(Math.Max(0, Math.Min(duration - 0.01, seconds)));
                ended = false;
                break;
            case "volume":
                double volume = double.Parse(command[1], CultureInfo.InvariantCulture);
                player.Volume = Math.Max(0, Math.Min(1, volume));
                break;
            case "quit":
                dispatcher.BeginInvokeShutdown(DispatcherPriority.Send);
                return;
        }
        Publish();
    }
}
