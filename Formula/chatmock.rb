class Chatmock < Formula
  include Language::Python::Virtualenv

  desc "OpenAI & Ollama compatible API powered by your ChatGPT plan"
  homepage "https://github.com/RayBytes/ChatMock"
  url "https://github.com/RayBytes/ChatMock/archive/refs/tags/v1.35.tar.gz"
  sha256 "0f710e100d325effe0cd927845e40bbc98aa7d20e6c3eefb87428c876b2168bf"
  license "MIT"
  head "https://github.com/RayBytes/ChatMock.git", branch: "main"

  depends_on "python@3.11"

  def install
    virtualenv_create(libexec, "python3.11")

    system libexec/"bin/pip", "install", "-r", "requirements.txt"

    libexec.install "chatmock/"
    libexec.install "chatmock.py"
    libexec.install "prompt.md"

    (bin/"chatmock").write <<~EOS
      #!/bin/bash
      set -e
      CHATMOCK_HOME="#{libexec}"
      export PYTHONPATH="#{libexec}:$PYTHONPATH"
      exec "#{libexec}/bin/python" "#{libexec}/chatmock.py" "$@"
    EOS

    chmod 0755, bin/"chatmock"
  end

  def caveats
    <<~EOS
      To get started with ChatMock:
        1. First, authenticate with your ChatGPT account:
           chatmock login

        2. Start the local API server:
           chatmock serve

        3. Use the API at http://127.0.0.1:8000/v1

      Note: ChatMock requires a paid ChatGPT Plus or Pro account to function.

      For more options and configuration:
           chatmock serve --help
    EOS
  end

  test do
    output = shell_output("#{bin}/chatmock --help 2>&1", 2)
    assert_match "ChatGPT Local", output
  end
end
