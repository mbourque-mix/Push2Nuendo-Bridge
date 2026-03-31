# Contributing to Push 2 / Nuendo Bridge

Thank you for your interest in contributing! This document explains how to contribute to this project.

## Developer Certificate of Origin (DCO)

This project uses the [Developer Certificate of Origin (DCO)](https://developercertificate.org/) to ensure that contributors have the right to submit the code they contribute.

By making a contribution to this project, you certify that you have the right to submit it under the GPL-3.0 license, in accordance with the DCO. The full text of the DCO can be found in the [DCO](DCO) file in the root of this repository.

### How to Sign Off Your Commits

Every commit must include a `Signed-off-by` line in the commit message. This is done by adding the `-s` flag when committing:

```bash
git commit -s -m "Your commit message"
```

This will add a line like this to your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

Make sure your `user.name` and `user.email` are configured in Git:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Signing Off Existing Commits

If you forgot to sign off a commit, you can amend your last commit:

```bash
git commit --amend -s
```

To sign off all commits in a branch:

```bash
git rebase --signoff main
```

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Sign off and commit (`git commit -s -m "Add my feature"`)
5. Push to your fork (`git push origin feature/my-feature`)
6. Open a Pull Request

## Pull Request Requirements

- All commits must be signed off (DCO)
- Code should follow the existing style
- Test your changes with both macOS and Windows if possible
- Update documentation if your changes affect user-facing features

## Reporting Issues

Please use the [GitHub Issues](https://github.com/mbourque-mix/Push2Nuendo-Bridge/issues) page to report bugs or request features. Include:

- Your operating system and version
- Nuendo/Cubase version
- Steps to reproduce the issue
- Relevant log output from `~/Library/Logs/Push2NuendoBridge.log`

## License

By contributing to this project, you agree that your contributions will be licensed under the GNU General Public License v3.0.
