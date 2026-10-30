param(
  [string]$Title = "GPTBOTPAD",
  [string]$OutputPath = "F:\gptbot\tmp\pad-output.txt",
  [int]$LifetimeSeconds = 60
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$directory = Split-Path -Parent $OutputPath
if ($directory) {
  New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$form = New-Object System.Windows.Forms.Form
$form.Text = $Title
$form.Width = 700
$form.Height = 500
$form.StartPosition = "CenterScreen"
$form.TopMost = $true

$textbox = New-Object System.Windows.Forms.TextBox
$textbox.Multiline = $true
$textbox.AcceptsReturn = $true
$textbox.AcceptsTab = $true
$textbox.Dock = "Fill"
$textbox.Font = New-Object System.Drawing.Font("Consolas", 12)
$form.Controls.Add($textbox)

$saveAction = {
  [System.IO.File]::WriteAllText($OutputPath, $textbox.Text, [System.Text.Encoding]::UTF8)
}

$textbox.add_TextChanged($saveAction)
$form.add_FormClosing($saveAction)
$form.add_Shown({
  $form.Activate()
  $textbox.Focus()
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = $LifetimeSeconds * 1000
$timer.add_Tick({
  $timer.Stop()
  $form.Close()
})
$timer.Start()

[System.Windows.Forms.Application]::Run($form)
