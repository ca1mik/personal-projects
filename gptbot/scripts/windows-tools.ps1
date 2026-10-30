param(
  [Parameter(Mandatory = $true)]
  [string]$Action,
  [string]$Title,
  [string]$Target,
  [string]$Text,
  [string]$Keys,
  [string]$Path,
  [string]$To,
  [string]$Subject,
  [string]$Body,
  [string]$Location,
  [string]$Start,
  [string]$Minutes,
  [string]$X,
  [string]$Y,
  [string]$Send
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class WinApi {
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

  [DllImport("user32.dll")]
  public static extern IntPtr GetForegroundWindow();

  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int X, int Y);

  [DllImport("user32.dll")]
  public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

  [DllImport("user32.dll")]
  public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
}
"@

$SW_RESTORE = 9
$SW_MINIMIZE = 6
$KEYEVENTF_KEYUP = 2
$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004

function Write-Json($payload) {
  $payload | ConvertTo-Json -Depth 8 -Compress
}

function Success($message, $extra = @{}) {
  Write-Json (@{ success = $true; message = $message } + $extra)
  exit 0
}

function Fail($message) {
  Write-Json @{ success = $false; message = $message }
  exit 1
}

function Get-WindowProcesses {
  Get-Process |
    Where-Object { $_.MainWindowTitle -and $_.MainWindowHandle -ne 0 } |
    Sort-Object MainWindowTitle
}

function Find-WindowByTitle([string]$WindowTitle) {
  if ([string]::IsNullOrWhiteSpace($WindowTitle)) {
    return $null
  }

  $query = $WindowTitle.ToLowerInvariant()
  return Get-WindowProcesses | Where-Object {
    $_.MainWindowTitle.ToLowerInvariant().Contains($query) -or $_.ProcessName.ToLowerInvariant().Contains($query)
  } | Select-Object -First 1
}

function Escape-SendKeysText([string]$RawText) {
  if ($null -eq $RawText) {
    return ""
  }

  $builder = New-Object System.Text.StringBuilder
  foreach ($char in $RawText.ToCharArray()) {
    switch ($char) {
      "{" { [void]$builder.Append("{{}") }
      "}" { [void]$builder.Append("{}}") }
      "+" { [void]$builder.Append("{+}") }
      "^" { [void]$builder.Append("{^}") }
      "%" { [void]$builder.Append("{%}") }
      "~" { [void]$builder.Append("{~}") }
      "(" { [void]$builder.Append("{(}") }
      ")" { [void]$builder.Append("{)}") }
      "[" { [void]$builder.Append("{[}") }
      "]" { [void]$builder.Append("{]}") }
      default { [void]$builder.Append($char) }
    }
  }

  return $builder.ToString()
}

function Get-TargetWindow([string]$WindowTitle) {
  if ([string]::IsNullOrWhiteSpace($WindowTitle)) {
    $handle = [WinApi]::GetForegroundWindow()
    if ($handle -eq [IntPtr]::Zero) {
      return $null
    }

    return Get-WindowProcesses | Where-Object { $_.MainWindowHandle -eq $handle } | Select-Object -First 1
  }

  return Find-WindowByTitle $WindowTitle
}

function Split-CommandTarget([string]$RawTarget) {
  $trimmed = $RawTarget.Trim()
  if ([string]::IsNullOrWhiteSpace($trimmed)) {
    return $null
  }

  if ($trimmed.StartsWith('"')) {
    $closingQuote = $trimmed.IndexOf('"', 1)
    if ($closingQuote -gt 0) {
      $filePath = $trimmed.Substring(1, $closingQuote - 1)
      $arguments = $trimmed.Substring($closingQuote + 1).Trim()
      return @{
        FilePath = $filePath
        Arguments = $arguments
      }
    }
  }

  $firstSpace = $trimmed.IndexOf(' ')
  if ($firstSpace -lt 0) {
    return @{
      FilePath = $trimmed
      Arguments = ""
    }
  }

  return @{
    FilePath = $trimmed.Substring(0, $firstSpace)
    Arguments = $trimmed.Substring($firstSpace + 1).Trim()
  }
}

function Convert-ToSendKeys([string]$RawKeys) {
  $tokens = $RawKeys.ToLowerInvariant().Split('+') | ForEach-Object { $_.Trim() } | Where-Object { $_ }

  if (-not $tokens.Count) {
    return $null
  }

  $modifiers = ""
  $mainToken = $tokens[-1]

  if ($tokens.Count -gt 1) {
    foreach ($token in $tokens[0..($tokens.Count - 2)]) {
      switch ($token) {
        "ctrl" { $modifiers += "^" }
        "control" { $modifiers += "^" }
        "alt" { $modifiers += "%" }
        "shift" { $modifiers += "+" }
        default { }
      }
    }
  }

  $map = @{
    "enter" = "{ENTER}"
    "esc" = "{ESC}"
    "escape" = "{ESC}"
    "tab" = "{TAB}"
    "space" = " "
    "delete" = "{DELETE}"
    "backspace" = "{BACKSPACE}"
    "up" = "{UP}"
    "down" = "{DOWN}"
    "left" = "{LEFT}"
    "right" = "{RIGHT}"
    "home" = "{HOME}"
    "end" = "{END}"
    "pgup" = "{PGUP}"
    "pgdn" = "{PGDN}"
  }

  if ($mainToken -match '^f([1-9]|1[0-2])$') {
    return $modifiers + "{" + $mainToken.ToUpperInvariant() + "}"
  }

  if ($map.ContainsKey($mainToken)) {
    return $modifiers + $map[$mainToken]
  }

  return $modifiers + $mainToken
}

function Resolve-VirtualKey([string]$Token) {
  $vkMap = @{
    "ctrl" = 0x11
    "control" = 0x11
    "alt" = 0x12
    "shift" = 0x10
    "win" = 0x5B
    "enter" = 0x0D
    "tab" = 0x09
    "esc" = 0x1B
    "escape" = 0x1B
    "space" = 0x20
    "delete" = 0x2E
    "backspace" = 0x08
    "up" = 0x26
    "down" = 0x28
    "left" = 0x25
    "right" = 0x27
    "home" = 0x24
    "end" = 0x23
    "pgup" = 0x21
    "pgdn" = 0x22
  }

  if ($vkMap.ContainsKey($Token)) {
    return $vkMap[$Token]
  }

  if ($Token -match '^[a-z]$') {
    return [byte][char]$Token.ToUpperInvariant()
  }

  if ($Token -match '^[0-9]$') {
    return [byte][char]$Token
  }

  if ($Token -match '^f([1-9]|1[0-2])$') {
    return 0x6F + [int]$Matches[1]
  }

  return $null
}

function Send-KeyCombo([string]$RawKeys) {
  $tokens = $RawKeys.ToLowerInvariant().Split('+') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  $codes = @()
  foreach ($token in $tokens) {
    $code = Resolve-VirtualKey $token
    if ($null -eq $code) {
      throw "Unsupported Win hotkey token: $token"
    }
    $codes += $code
  }

  foreach ($code in $codes) {
    [WinApi]::keybd_event([byte]$code, 0, 0, 0)
  }

  Start-Sleep -Milliseconds 120

  [array]::Reverse($codes)
  foreach ($code in $codes) {
    [WinApi]::keybd_event([byte]$code, 0, $KEYEVENTF_KEYUP, 0)
  }
}

try {
  switch ($Action) {
    "list_windows" {
      $windows = Get-WindowProcesses | Select-Object Id, ProcessName, MainWindowTitle | ForEach-Object {
        @{
          pid = $_.Id
          process = $_.ProcessName
          title = $_.MainWindowTitle
        }
      }

      Success "OK" @{ windows = $windows }
    }

    "focus_window" {
      $window = Get-TargetWindow $Title
      if (-not $window) {
        Fail "Window not found"
      }

      [WinApi]::ShowWindowAsync($window.MainWindowHandle, $SW_RESTORE) | Out-Null
      Start-Sleep -Milliseconds 150
      [WinApi]::SetForegroundWindow($window.MainWindowHandle) | Out-Null
      Success "Window focused: $($window.MainWindowTitle)"
    }

    "minimize_window" {
      $window = Get-TargetWindow $Title
      if (-not $window) {
        Fail "Window not found"
      }

      [WinApi]::ShowWindowAsync($window.MainWindowHandle, $SW_MINIMIZE) | Out-Null
      Success "Window minimized: $($window.MainWindowTitle)"
    }

    "restore_window" {
      $window = Get-TargetWindow $Title
      if (-not $window) {
        Fail "Window not found"
      }

      [WinApi]::ShowWindowAsync($window.MainWindowHandle, $SW_RESTORE) | Out-Null
      Start-Sleep -Milliseconds 100
      [WinApi]::SetForegroundWindow($window.MainWindowHandle) | Out-Null
      Success "Window restored: $($window.MainWindowTitle)"
    }

    "open_target" {
      if ([string]::IsNullOrWhiteSpace($Target)) {
        Fail "Target is empty"
      }

      $command = Split-CommandTarget $Target
      if (-not $command) {
        Fail "Failed to parse target"
      }

      if ([string]::IsNullOrWhiteSpace($command.Arguments)) {
        Start-Process -FilePath $command.FilePath | Out-Null
      } else {
        Start-Process -FilePath $command.FilePath -ArgumentList $command.Arguments | Out-Null
      }

      Success "Started: $Target"
    }

    "send_keys" {
      if ([string]::IsNullOrWhiteSpace($Keys)) {
        Fail "Keys are empty"
      }

      try {
        Send-KeyCombo $Keys
      } catch {
        $sendKeys = Convert-ToSendKeys $Keys
        if (-not $sendKeys) {
          Fail "Failed to parse keys"
        }

        [System.Windows.Forms.SendKeys]::SendWait($sendKeys)
      }

      Success "Keys sent: $Keys"
    }

    "type_text" {
      if ([string]::IsNullOrWhiteSpace($Text)) {
        Fail "Text is empty"
      }

      $clipboardBackup = $null
      if ([System.Windows.Forms.Clipboard]::ContainsText()) {
        $clipboardBackup = [System.Windows.Forms.Clipboard]::GetText()
      }

      [System.Windows.Forms.Clipboard]::SetText($Text)
      Send-KeyCombo "ctrl+v"
      Start-Sleep -Milliseconds 100

      if ($null -ne $clipboardBackup) {
        [System.Windows.Forms.Clipboard]::SetText($clipboardBackup)
      }

      Success "Text typed"
    }

    "click" {
      if ([string]::IsNullOrWhiteSpace($X) -or [string]::IsNullOrWhiteSpace($Y)) {
        Fail "Coordinates are required"
      }

      [WinApi]::SetCursorPos([int]$X, [int]$Y) | Out-Null
      Start-Sleep -Milliseconds 80
      [WinApi]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
      [WinApi]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
      Success "Clicked at $X,$Y"
    }

    "screenshot" {
      if ([string]::IsNullOrWhiteSpace($Path)) {
        Fail "Path is empty"
      }

      $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
      $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
      $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
      $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
      $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
      $graphics.Dispose()
      $bitmap.Dispose()
      Success "Screenshot saved" @{ path = $Path }
    }

    "draft_email" {
      $outlook = New-Object -ComObject Outlook.Application
      $mail = $outlook.CreateItem(0)
      $mail.To = $To
      $mail.Subject = $Subject
      $mail.Body = $Body

      if ($Send -eq "true") {
        $mail.Send()
      } else {
        $mail.Save()
      }

      [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($mail)
      [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($outlook)
      [GC]::Collect()
      [GC]::WaitForPendingFinalizers()

      if ($Send -eq "true") {
        Success "Email sent to: $To"
      }

      Success "Email draft created for: $To"
    }

    "create_event" {
      $outlook = New-Object -ComObject Outlook.Application
      $appointment = $outlook.CreateItem(1)
      $appointment.Subject = $Subject
      $appointment.Start = [datetime]::Parse($Start)
      $appointment.Duration = if ([string]::IsNullOrWhiteSpace($Minutes)) { 60 } else { [int]$Minutes }
      $appointment.Location = $Location
      $appointment.Body = $Body
      $appointment.BusyStatus = 2
      $appointment.ReminderSet = $true
      $appointment.Save()

      [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($appointment)
      [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($outlook)
      [GC]::Collect()
      [GC]::WaitForPendingFinalizers()

      Success "Calendar event created: $Subject"
    }

    default {
      Fail "Unknown action: $Action"
    }
  }
} catch {
  Fail $_.Exception.Message
}
