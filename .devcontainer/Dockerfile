FROM python:3.11-slim

# Install essential tools and fish shell
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends git curl ca-certificates gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add fish shell repository and install fish
RUN echo 'deb http://download.opensuse.org/repositories/shells:/fish:/release:/3/Debian_11/ /' | tee /etc/apt/sources.list.d/shells:fish:release:3.list \
    && curl -fsSL https://download.opensuse.org/repositories/shells:fish:release:3/Debian_11/Release.key | gpg --dearmor | tee /etc/apt/trusted.gpg.d/shells_fish_release_3.gpg > /dev/null \
    && apt-get update \
    && apt-get install -y fish \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Set fish as default shell for the user
RUN chsh -s /usr/bin/fish $USERNAME

# Set up the workspace
WORKDIR /workspace

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add some basic fish configuration
RUN mkdir -p /home/$USERNAME/.config/fish \
    && echo "set -g fish_greeting ''" > /home/$USERNAME/.config/fish/config.fish \
    && echo "alias ll='ls -la'" >> /home/$USERNAME/.config/fish/config.fish \
    && echo "alias py='python'" >> /home/$USERNAME/.config/fish/config.fish \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME/.config

# Set the default user
USER $USERNAME