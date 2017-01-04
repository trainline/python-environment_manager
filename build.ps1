function CreateChocolateyPackage {
    param(
        [string] $PackageId,
        [string] $Version
    )
    $OutputDirectory = "$TempDirectory\output"
    $DataDirectory = "$OutputDirectory\data\"

    Write-Host "Setting up $OutputDirectory for package staging..."
    New-Item $OutputDirectory -type directory
	
	Write-Host "Copying content of $RootDirectory\windows\ to temporary output directory..."
    Copy-Item $RootDirectory\windows\* $OutputDirectory -Recurse
	
	Write-Host "Copying required content of the repository to temporary output directory..."
	$items = Get-ChildItem $RootDirectory\* -Recurse | ?{ $_.fullname -notmatch "$RegexRoot\\temp\\?" }
	$pathlength = (Get-Item -Path ".\" -Verbose).FullName.Length
	
	foreach($item in $items) {
        $target = Join-Path $DataDirectory $item.FullName.SubString($pathlength)
		Copy-Item -Path $item.FullName -Destination $target
    }
	
    Write-Host "Updating version in $OutputDirectory\package.nuspec to $Version..."
    $NuspecFile = @(Get-Item $OutputDirectory\package.nuspec)
    $Nuspec = [xml] (Get-Content $NuspecFile)
    $Nuspec.package.metadata.version = $Version
	$Nuspec.package.metadata.id = $PackageId
    $Nuspec.Save($NuspecFile)

    Write-Host "Making sure Chocolatey is installed..."
    if ((Test-Path env:\CHOCOLATEYINSTALL) -and (Test-Path $env:CHOCOLATEYINSTALL)) {
        $ChocolateyPath = $env:CHOCOLATEYINSTALL
    }
    else {
        throw "Chocolatey is not installed."
    }

    Write-Host "Creating Chocolatey package with choco.exe..."
    Set-Location $OutputDirectory
    & choco pack package.nuspec
    if ($LASTEXITCODE -ne 0) {
        throw "Error creating Chocolatey package."
    }
    Set-Location $RootDirectory
}

function PublishChocolateyPackage {
    param(
        [string] $PackageId,
        [string] $Version
    )
    if (Test-Path -path env:\TEAMCITY_VERSION) {
        $ApiKey = "repo-pkgs-build:gd2VsbC4NC"
        $OutputDirectory = "$TempDirectory\output"

        & nuget setApiKey $ApiKey -Source http://push.pkgs.ttldev
        if ($LASTEXITCODE -ne 0) {
            throw "Error setting API key for http://push.pkgs.ttldev Artifactory repository."
        }

        & choco push $OutputDirectory\$PackageId.$Version.nupkg -Source http://push.pkgs.ttldev
        if ($LASTEXITCODE -ne 0) {
            throw "Error publishing $OutputDirectory\$PackageId.$Version.nupkg to Artifactory."
        }
    }
    else {
        Write-Host "Skipping push to Artifactory..."
    }
}

try {
    Write-Host "Cleaning up temporary directory..."
    $RootDirectory = (Get-Item -Path ".\" -Verbose).FullName
    $RegexRoot = $RootDirectory.Replace("\","\\")
    $TempDirectory = "$RootDirectory\temp"
    if (Test-Path $TempDirectory) {
        Remove-Item $TempDirectory -Recurse -Force
    }

    $PackageId = "ttl-python-environment_manager"
	#$datetime = Get-Date -UFormat "%y%m%d%H%M%S"
	$Version = "0.1.0." + $env:BUILD_NUMBER
    if ($Version -eq $null) {
        $Version = "0.1.0"
    }

    Write-Host "Creating Chocolatey package..."
    CreateChocolateyPackage $PackageId $Version
    Write-Host "Publishing Chocolatey package to Artifactory..."
    PublishChocolateyPackage $PackageId $Version
} 
catch {
    Write-Host "FATAL EXCEPTION: $_"
    exit 1
}