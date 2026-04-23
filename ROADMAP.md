# Development Roadmap

Things planned for future releases or ideas are written here. None of these lists are final or cover all future updates, unless stated.

## 0.1.x branch of releases

Upcoming minor versions are planned to receive:

- Sensors added to the Ingenium Smart Touch device (background, SiDE version, kernel version etc.)
- Support for list "Scenario" and detect activations on the Ingenium Smart Touch device
- Improved device detection, potentially broader support (VIIP product range ?)
- Integration reload and re-configuration options
- Smart detection and clean-up of stale config entries
- Continued improvements to stability, performance and small features

## First 0.2.0 release

First release with project in its intended form, fit for general public use and publication in HACS.

Major Project improvemnents:

- Separate the Ingenium http/BUSing library into it's own project
- Provide UI (E2E) testing framework
- Meet hass **bronze** quality scale [requirements](https://developers.home-assistant.io/docs/core/integration-quality-scale/) at minimum

Rewrite [README.md](/README.md), add at minimum:

- Explanation of project scope, devices in the Ingenium ecosystem that this project is intended for and those that are excluded
- Installation instructions (git checkout, local install and HACS)
- Development workflow/instructions
- Development documentation, ingenium hardware references and integration architecture description
- Instructions for contributing (code, reporting issues)

Ingenium component improvements:

- Separate Ingenium device BUSing inteface logic
- BUSing device initialization on integration startup, so device status shows up immediately
- Lock down integration config entry structure with (Type-)Class
