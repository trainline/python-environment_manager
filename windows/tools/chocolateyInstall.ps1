$PackageDirectory = $env:chocolateyPackageFolder
$InstallDirectory = "C:/ProgramData/python-environment_manager"

try {
    Write-Host "Checking if install directory $InstallDirectory exists..."
    if (-Not (Test-Path $InstallDirectory)) {
        Write-Host "Creating install directory $InstallDirectory..."
        New-Item $InstallDirectory -type directory
    }
    else {
        Write-Host "Cleaning up install directory $InstallDirectory..."
        Remove-Item $InstallDirectory\* -Recurse
    }

    Write-Host "Copying files from $PackageDirectory to $InstallDirectory..."
    Copy-Item $PackageDirectory\data\* $InstallDirectory -Recurse -Force
}
catch {
  throw $_.Exception
}
