#    Friendly Telegram (telegram userbot)
#    Copyright (C) 2018-2019 The Authors

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import shlex

from . import utils


class CommandDispatcher:
    def __init__(self, modules, db, bot):
        self._modules = modules
        self._db = db
        self._bot = bot

    async def handle_command(self, event):
        """Handle all commands"""
        # Empty string evaluates to False, so the `or` activates
        prefixes = self._db.get(__name__, "command_prefix", False) or ["."]
        if isinstance(prefixes, str):
            prefixes = [prefixes]  # legacy db migration
        if not hasattr(event, "message") or getattr(event.message, "message", "") == "":
            return
        prefix = None
        for possible_prefix in prefixes:
            if event.message.startswith(possible_prefix):
                prefix = possible_prefix
                break
        if prefix is None:
            return
        logging.debug("Incoming command!")
        if not event.message:
            logging.debug("Ignoring command with no text.")
            return
        if event.sticker:
            logging.debug("Ignoring invisible command (with sticker).")
        if event.via_bot_id:
            logging.debug("Ignoring inline bot.")
            return
        message = utils.censor(event.message)
        blacklist_chats = self._db.get(__name__, "blacklist_chats", [])
        whitelist_chats = self._db.get(__name__, "whitelist_chats", [])
        whitelist_modules = self._db.get(__name__, "whitelist_modules", [])
        if utils.get_chat_id(message) in blacklist_chats or (whitelist_chats and utils.get_chat_id(message) not in
                                                             whitelist_chats) or message.from_id is None:
            logging.debug("Message is blacklisted")
            return
        if not self._bot and len(message.message) > len(prefix) and message.message[:len(prefix) * 2] == prefix * 2 \
                and message.message != len(message.message) // len(prefix) * prefix:
            # Allow escaping commands using .'s
            await message.edit(utils.escape_html(message.message[len(prefix):]))
        logging.debug(message)
        # Make sure we don't get confused about spaces or other stuff in the prefix
        message.message = message.message[len(prefix):]
        if not message.message:
            return  # Message is just the prefix
        try:
            shlex.split(message.message)  # TODO reconsider
        except ValueError as e:
            await message.edit("Invalid Syntax: " + str(e))
            return
        command = message.message.split(maxsplit=1)[0]
        logging.debug(command)
        txt, func = self._modules.dispatch(command)
        message.message = txt + message.message[len(command):]
        if func is not None:
            if str(utils.get_chat_id(message)) + "." + func.__self__.__module__ in blacklist_chats:
                logging.debug("Command is blacklisted in chat")
                return
            if whitelist_modules and not (str(utils.get_chat_id(message)) + "."
                                          + func.__self__.__module__ in whitelist_modules):
                logging.debug("Command is not whitelisted in chat")
                return
            try:
                await func(message)
            except Exception as e:
                logging.exception("Command failed")
                try:
                    await message.edit("<b>Request failed! Request was</b> <code>" + utils.escape_html(message.message)
                                       + "</code><b>. Please report it in the support group "
                                       "(</b><code>{0}support</code><b>) along with the logs "
                                       "(</b><code>{0}logs error</code><b>)</b>".format(prefix))
                finally:
                    raise e

    async def handle_incoming(self, event):
        """Handle all incoming messages"""
        logging.debug("Incoming message!")
        message = utils.censor(event.message)
        blacklist_chats = self._db.get(__name__, "blacklist_chats", [])
        whitelist_chats = self._db.get(__name__, "whitelist_chats", [])
        whitelist_modules = self._db.get(__name__, "whitelist_modules", [])
        if utils.get_chat_id(message) in blacklist_chats or (whitelist_chats and utils.get_chat_id(message) not in
                                                             whitelist_chats) or message.from_id is None:
            logging.debug("Message is blacklisted")
            return
        for func in self._modules.watchers:
            if str(utils.get_chat_id(message)) + "." + func.__self__.__module__ in blacklist_chats:
                logging.debug("Command is blacklisted in chat")
                return
            if whitelist_modules and not (str(utils.get_chat_id(message)) + "."
                                          + func.__self__.__module__ in whitelist_modules):
                logging.debug("Command is not whitelisted in chat")
                return
            try:
                await func(message)
            except Exception:
                logging.exception("Error running watcher")
