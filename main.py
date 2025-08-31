import os
import logging
import asyncio
from pathlib import Path
from mega import Mega
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from typing import List, Optional

# Bot configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Get from @BotFather
AUTHORIZED_USERS = [123456789]  # Add your user ID here

class TelegramMegaDownloadBot:
    def __init__(self, download_dir: str = "downloads"):
        """
        Initialize Telegram Mega Download Bot
        
        Args:
            download_dir: Directory to save downloaded files
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        # Initialize Mega client
        self.mega = Mega()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Telegram Mega Download Bot initialized")

    async def download_from_public_link(self, mega_link: str, chat_id: int) -> Optional[str]:
        """
        Download file from public Mega link and return file path
        
        Args:
            mega_link: Public Mega share link
            chat_id: Telegram chat ID for progress updates
            
        Returns:
            Path to downloaded file or None if failed
        """
        try:
            # Send initial message
            message = await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"🔍 Processing Mega link...\n`{mega_link}`",
                parse_mode='Markdown'
            )
            
            # Get public file information
            file_info = self.mega.get_public_file_info(mega_link)
            if not file_info:
                await message.edit_text("❌ Invalid Mega link or file not found")
                return None
            
            file_name = file_info['name']
            file_size = file_info['size']
            
            await message.edit_text(
                f"📁 File: `{file_name}`\n"
                f"📊 Size: `{self.format_size(file_size)}`\n"
                f"⏬ Starting download...",
                parse_mode='Markdown'
            )
            
            # Download the file
            download_path = self.download_dir / file_name
            
            downloaded_file = self.mega.download_from_url(
                mega_link, 
                dest_path=str(self.download_dir),
                dest_filename=file_name
            )
            
            await message.edit_text(
                f"✅ Download completed!\n"
                f"📁 File: `{file_name}`\n"
                f"💾 Saved to: `{downloaded_file}`",
                parse_mode='Markdown'
            )
            
            return downloaded_file
            
        except Exception as e:
            error_msg = f"❌ Download failed: {str(e)}"
            self.logger.error(error_msg)
            if 'message' in locals():
                await message.edit_text(error_msg)
            return None

    def format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
            
        welcome_text = """
        🤖 Mega Download Bot
        
        Send me a Mega.nz public link and I'll download it for you!
        
        Supported links:
        • https://mega.nz/file/...
        • https://mega.nz/folder/...
        
        Commands:
        /start - Show this help
        /download [link] - Download from Mega link
        /batch - Upload a text file with multiple links
        """
        
        await update.message.reply_text(welcome_text)

    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /download command"""
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
            
        if not context.args:
            await update.message.reply_text("Please provide a Mega link after the command.\nExample: /download https://mega.nz/file/...")
            return
            
        mega_link = context.args[0]
        if not mega_link.startswith('https://mega.nz/'):
            await update.message.reply_text("❌ Please provide a valid Mega.nz link")
            return
            
        # Download the file
        downloaded_file = await self.download_from_public_link(mega_link, update.effective_chat.id)
        
        if downloaded_file:
            # Send the file back to user
            try:
                with open(downloaded_file, 'rb') as file:
                    await update.message.reply_document(
                        document=InputFile(file, filename=os.path.basename(downloaded_file)),
                        caption=f"✅ Download completed: {os.path.basename(downloaded_file)}"
                    )
                # Clean up
                os.remove(downloaded_file)
            except Exception as e:
                await update.message.reply_text(f"❌ Error sending file: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle direct messages with Mega links"""
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
            
        message_text = update.message.text
        
        if message_text.startswith('https://mega.nz/'):
            # Download the file
            downloaded_file = await self.download_from_public_link(message_text, update.effective_chat.id)
            
            if downloaded_file:
                # Send the file back to user
                try:
                    with open(downloaded_file, 'rb') as file:
                        await update.message.reply_document(
                            document=InputFile(file, filename=os.path.basename(downloaded_file)),
                            caption=f"✅ Download completed: {os.path.basename(downloaded_file)}"
                        )
                    # Clean up
                    os.remove(downloaded_file)
                except Exception as e:
                    await update.message.reply_text(f"❌ Error sending file: {str(e)}")
        else:
            await update.message.reply_text("Please send a valid Mega.nz public link")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text files with multiple links"""
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
            
        document = update.message.document
        if document.mime_type == 'text/plain' or document.file_name.endswith('.txt'):
            # Download the text file
            file = await document.get_file()
            temp_file = f"temp_{document.file_id}.txt"
            await file.download_to_drive(temp_file)
            
            # Read links from file
            with open(temp_file, 'r') as f:
                links = [line.strip() for line in f if line.strip() and line.startswith('https://mega.nz/')]
            
            os.remove(temp_file)
            
            if not links:
                await update.message.reply_text("❌ No valid Mega links found in the file")
                return
                
            await update.message.reply_text(f"Found {len(links)} valid Mega links. Starting batch download...")
            
            # Download each file
            for i, link in enumerate(links, 1):
                await update.message.reply_text(f"📥 Downloading {i}/{len(links)}...")
                downloaded_file = await self.download_from_public_link(link, update.effective_chat.id)
                
                if downloaded_file:
                    try:
                        with open(downloaded_file, 'rb') as file:
                            await update.message.reply_document(
                                document=InputFile(file, filename=os.path.basename(downloaded_file)),
                                caption=f"✅ {i}/{len(links)}: {os.path.basename(downloaded_file)}"
                            )
                        os.remove(downloaded_file)
                    except Exception as e:
                        await update.message.reply_text(f"❌ Error sending file {i}: {str(e)}")
                
                # Delay between downloads to avoid rate limiting
                await asyncio.sleep(2)
                
            await update.message.reply_text("✅ Batch download completed!")
        else:
            await update.message.reply_text("Please upload a text file (.txt) containing Mega links")

    def run_bot(self, token: str):
        """Start the Telegram bot"""
        self.application = Application.builder().token(token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("download", self.download_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        self.logger.info("Bot is running...")
        self.application.run_polling()

# Main execution
if __name__ == "__main__":
    # Replace with your bot token from @BotFather
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # Add your user ID (send /start to @userinfobot on Telegram to get your ID)
    AUTHORIZED_USERS = [123456789]  # Replace with your actual user ID
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your bot token in the BOT_TOKEN variable")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Copy the token and replace 'YOUR_BOT_TOKEN_HERE'")
        print("3. Add your user ID to AUTHORIZED_USERS list")
    else:
        bot = TelegramMegaDownloadBot()
        bot.run_bot(BOT_TOKEN)
