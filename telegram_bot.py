# -*- coding: utf-8 -*-
#!/usr/bin/env python3
from __future__ import unicode_literals

import telegram
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, Filters
from telegram.error import TelegramError, Unauthorized
import logging

import os
import sys
import traceback
from threading import Thread
import shutil
import pickle
import datetime
from collections import defaultdict

from functools import wraps

with open("api_key.txt", 'r') as f:
    TOKEN = f.read().rstrip()

# Format is mmddyyyy and then additional letters if I need a hotfix.
PATCHNUMBER = "10272020"

ADMIN = [539621524]

TITLE, DESCRIPTION, REWARD = range(3)

def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

ERROR_LOGGER = setup_logger("error_logger", "error_logs.log")

"""
Contains:

sidequests - Key is telegram_id, value is a list as [sidequest title, sidequest description, sidequest reward, list of accepters by Telegram ID].
users - A list of (telegram_id, name) tuples.
patches - A list of strings representing the patch history.
archives - Key is questgiver_id, value is a list as [title, description, reward, [accepters]].
"""
sidequest_database = pickle.load(open("./sidequestdatabase", "rb")) if os.path.isfile("./sidequestdatabase") else {}

bot = telegram.Bot(token=TOKEN)


def send_message(chat_id, text, photo=None):
    try:
        if len(text) > 4096:
            for x in range(0, len(text), 4096):
                bot.send_message(chat_id=chat_id, text=text[x:x + 4096], parse_mode=telegram.ParseMode.HTML)
        else:
            bot.send_message(chat_id=chat_id, text=text, parse_mode=telegram.ParseMode.HTML)

        if photo is not None:
            bot.send_photo(chat_id=chat_id, photo=photo, parse_mode=telegram.ParseMode.HTML)
    except Unauthorized as u:
        # Just ignore that person for now.
        pass
    except TelegramError as e:
        raise e


def static_handler(command):
    text = open("static_responses/{}.txt".format(command), "r").read()
    return CommandHandler(command,
        lambda update, context: send_message(update.message.chat.id, text))


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped


def send_patchnotes():
    path = "./static_responses/patchnotes_" + PATCHNUMBER + ".txt"

    if PATCHNUMBER in sidequest_database["patches"] or not os.path.isfile(path):
        return

    text = open(path, "r").read()

    for (telegram_id, name) in sidequest_database["users"]:
        send_message(telegram_id, text)

    sidequest_database["patches"].append(PATCHNUMBER)


def get_username(user):
    username = ""
    if user.username is not None:
        username = user.username
        if user.first_name is not None:
            username += " (" + user.first_name
        if user.last_name is not None:
            username += " " + user.last_name + ")"
        else:
            username += ")"
    else:
        if user.first_name is not None:
            username += user.first_name
        if user.last_name is not None:
            username += " " + user.last_name
    return username


def check_profile_existence(id):
    for cur_id, name in sidequest_database["users"]:
        if cur_id == id:
            return True
    return False


def get_name_from_database(id):
    for cur_id, name in sidequest_database["users"]:
        if cur_id == id:
            return name
    return ""


def users_handler(update, context):
    chat_id = update.message.chat.id
    # Callback data for display is:
    # [SHOWALL (header)]
    buttons = [[telegram.InlineKeyboardButton(text="Show All", callback_data="SHOWALL")]]

    text = "Users:"
    for id, name in sidequest_database["users"]:
        # Callback data for display is:
        # [DISPLAY (header), telegram_id]
        buttons.append([telegram.InlineKeyboardButton(text=name, callback_data="DISPLAY,%d" % id)])

    bot.send_message(chat_id=chat_id,
                     text=text,
                     reply_markup=telegram.InlineKeyboardMarkup(buttons),
                     parse_mode=telegram.ParseMode.HTML)


def make_display_buttons(telegram_id, requester_id):
    buttons = []
    count = 0

    if telegram_id == requester_id:
        for title, description, reward, accepters in sidequest_database["sidequests"][telegram_id]:
            buttons.append(
                [
                    # Callback data for show is:
                    # [SHOW (header), Sidequest Giver Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text=title if title != "" else "[NO TITLE]",
                                                  callback_data="SHOW,%s,%s" % (telegram_id, count))
                ]
            )
            buttons.append(
                [
                    # Callback data for delete is:
                    # [DELETE (header), Sidequest Owner Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text="❌", callback_data="DELETE,%s,%s" % (telegram_id, count)),
                    # Callback data for archive is:
                    # [ARCHIVE (header), Sidequest Owner Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text="🔒", callback_data="ARCHIVE,%s,%s" % (telegram_id, count)),
                    # Callback data for edit is:
                    # [EDIT (header), Sidequest Owner Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text="✏️", callback_data="EDIT,%s,%s" % (telegram_id, count)),
                    # Callback data for listing the accepters is:
                    # [LIST (header), Sidequest Owner Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text="≡ (%s)" % len(accepters), callback_data="LIST,%s,%s" % (telegram_id, count))
                ]
            )
            count += 1
    else:
        for title, description, reward, accepters in sidequest_database["sidequests"][telegram_id]:
            buttons.append(
                [
                    # Callback data for show is:
                    # [SHOW (header), Sidequest Giver Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text=title if title != "" else "[NO TITLE]",
                                                  callback_data="SHOW,%s,%s" % (telegram_id, count))
                ]
            )
            buttons.append(
                [
                    # Callback data for listing the accepters is:
                    # [LIST (header), Sidequest Owner Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text="≡ (%s)" % len(accepters), callback_data="LIST,%s,%s" % (telegram_id, count)),
                    # Callback data for toggle is:
                    # [TOGGLE (header), Sidequest Giver Telegram ID, Sidequest ID]
                    telegram.InlineKeyboardButton(text="⬜" if requester_id not in accepters else "☑️",
                                                  callback_data="TOGGLE,%s,%s" % (telegram_id, count))
                ]
            )
            count += 1

    return buttons


def make_my_sidequest_buttons(telegram_id):
    buttons = []

    for id, name in sidequest_database["users"]:
        if id != telegram_id:
            count = 0
            for title, description, reward, accepters in sidequest_database["sidequests"][id]:
                if telegram_id in accepters:
                    buttons.append(
                        [
                            # Callback data for show is:
                            # [SHOW (header), Sidequest Giver Telegram ID, Sidequest ID]
                            telegram.InlineKeyboardButton(text=title,
                                                          callback_data="SHOW,%s,%s" % (id, count))
                        ]
                    )
                    buttons.append(
                        [
                            # Callback data for delete is:
                            # [DELETE (header), Sidequest Owner Telegram ID, Sidequest ID]
                            telegram.InlineKeyboardButton(text="❌", callback_data="DELETE,%s,%s" % (id, count)),
                            # Callback data for archive is:
                            # [ARCHIVE (header), Sidequest Owner Telegram ID, Sidequest ID]
                            telegram.InlineKeyboardButton(text="🔒", callback_data="ARCHIVE,%s,%s" % (id, count)),
                            # Callback data for edit is:
                            # [EDIT (header), Sidequest Owner Telegram ID, Sidequest ID]
                            telegram.InlineKeyboardButton(text="✏️", callback_data="EDIT,%s,%s" % (id, count)),
                            # Callback data for toggle is:
                            # [TOGGLE (header), Sidequest Giver Telegram ID, Sidequest ID]
                            telegram.InlineKeyboardButton(text="⬜" if telegram_id not in accepters else "☑️",
                                                          callback_data="TOGGLE,%s,%s" % (id, count))
                        ]
                    )
                count += 1

    return buttons


def my_sidequests_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return

    bot.send_message(chat_id=chat_id,
                     text="<b>Your Sidequests:</b>\n\n",
                     reply_markup=telegram.InlineKeyboardMarkup(make_my_sidequest_buttons(user.id)),
                     parse_mode=telegram.ParseMode.HTML)


def display_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    if len(context.args) < 1:
        username = ""
        for (id, name) in sidequest_database["users"]:
            if id == user.id:
                username = name
                break

        if username == "":
            send_message(chat_id, "You haven't joined using /am!")
            return

        bot.send_message(chat_id=chat_id,
                         text="<b>Sidequests for %s:</b>\n\n" % username,
                         reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(user.id, user.id)),
                         parse_mode=telegram.ParseMode.HTML)
        return

    if len(context.args) > 1:
        send_message(chat_id, "Usage: /display [name]")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        user_id = -1
        name = " ".join(context.args)
        for i, tup in enumerate(sidequest_database["users"]):
            if name.lower() in tup[1].lower():
                user_id = i
                break
        if user_id == -1:
            send_message(chat_id, "Error: Could not find a matching name!")
            return

    if user_id < 0 or user_id >= len(sidequest_database["users"]):
        send_message(chat_id, "That (%s) is not a valid ID in the range [%s, %s)!" %
                     (user_id, 0, len(sidequest_database["users"])))
        return

    bot.send_message(chat_id=chat_id,
                     text="<b>Sidequests for %s:</b>\n\n" % sidequest_database["users"][user_id][1],
                     reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(sidequest_database["users"][user_id][0], user.id)),
                     parse_mode=telegram.ParseMode.HTML)


def add_me_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    if len(context.args) == 0:
        username = get_username(user)
    else:
        username = " ".join(context.args)

    for id, name in sidequest_database["users"]:
        if id == user.id:
            send_message(chat_id, "You're already in the database!")
            return

    sidequest_database["users"].append((user.id, username))
    # Sort by name
    sidequest_database["users"] = sorted(sidequest_database["users"], key=lambda x: str(x[1]).lower())

    send_message(chat_id, "You've been added! Make sure to send me a DM to be able to get messages!")


def remove_me_confirmed_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    for id, name in sidequest_database["users"]:
        if id == user.id:
            sidequest_database["users"].remove((id, name))
            break

    for id in sidequest_database["sidequests"].keys():
        if id == user.id:
            del sidequest_database["sidequests"][user.id]
            break
        else:
            for title, description, reward, accepters in sidequest_database["sidequests"][id]:
                if user.id in accepters:
                    accepters.remove(user.id)

    send_message(chat_id, "You've been removed!")


def remove_me_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    if user.id not in [t[0] for t in sidequest_database["users"]]:
        send_message(chat_id, "You haven't made an account by joining using /am!")
        return

    send_message(chat_id, "Are you sure you want to leave? If so, use /rmc.")


def ban_handler(update, context):
    chat_id = update.message.chat.id

    if len(context.args) < 1:
        send_message(chat_id, "Usage: /ban {ID from /users or name}")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        user_id = -1
        name = str(context.args[0])
        for i, tup in enumerate(sidequest_database["users"]):
            if name.lower() in tup[1].lower():
                user_id = i
                break
        if user_id == -1:
            send_message(chat_id, "Error: Could not find a matching name!")
            return

    if user_id < 0 or user_id >= len(sidequest_database["users"]):
        send_message(chat_id, "That (%s) is not a valid ID in the range [%s, %s)!" %
                     (user_id, 0, len(sidequest_database["users"])))
        return

    telegram_id = sidequest_database["users"][user_id][0]

    for id, username in sidequest_database["users"]:
        if id == telegram_id:
            sidequest_database["users"].remove((telegram_id, username))
            break

    for id in sidequest_database["sidequests"].keys():
        if id == telegram_id:
            del sidequest_database["sidequests"][telegram_id]
            break

    send_message(chat_id, "That user has been removed!")


def show_all_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    for id, name in sidequest_database["users"]:
        if id != user.id and len(sidequest_database["sidequests"][id]) > 0:
            bot.send_message(chat_id=chat_id,
                             text="<b>Sidequests for %s:</b>\n\n" % name,
                             reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(id, user.id)),
                             parse_mode=telegram.ParseMode.HTML)


def button_handler(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = int(query.from_user.id)

    split_data = query.data.split(",")

    if not check_profile_existence(user_id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    if split_data[0] == "TOGGLE":
        questgiver_id = int(split_data[1])
        quest_id = int(split_data[2])

        if questgiver_id == user_id:
            send_message(chat_id, "You can't toggle your own sidequests!")
            return

        if user_id in sidequest_database["sidequests"][questgiver_id][quest_id][3]:
            sidequest_database["sidequests"][questgiver_id][quest_id][3].remove(user_id)
            send_message(questgiver_id, "%s is no longer doing sidequest %s." % (get_name_from_database(user_id), sidequest_database["sidequests"][questgiver_id][quest_id][0]))
            send_message(user_id, "You are no longer doing sidequest %s for %s." % (sidequest_database["sidequests"][questgiver_id][quest_id][0], get_name_from_database(questgiver_id)))
        else:
            sidequest_database["sidequests"][questgiver_id][quest_id][3].append(user_id)
            send_message(questgiver_id, "%s has accepted your sidequest %s." % (get_name_from_database(user_id), sidequest_database["sidequests"][questgiver_id][quest_id][0]))
            send_message(user_id, "You have accepted sidequest %s for %s." % (sidequest_database["sidequests"][questgiver_id][quest_id][0], get_name_from_database(questgiver_id)))

        bot.edit_message_text(chat_id=chat_id,
                              text="<b>Sidequests for %s:</b>\n\n" % get_name_from_database(questgiver_id),
                              message_id=query.message.message_id,
                              reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(questgiver_id, user_id)),
                              parse_mode="HTML")
    elif split_data[0] == "DELETE":
        questgiver_id = int(split_data[1])
        quest_id = int(split_data[2])

        if user_id != questgiver_id:
            send_message(chat_id, "That's not your sidequest list!")
            return

        title, description, reward, accepters = sidequest_database["sidequests"][questgiver_id][quest_id]

        for accepter in accepters:
            send_message(accepter, "The sidequest, %s by %s, you were on was just deleted!" % (title, get_name_from_database(questgiver_id)))

        del sidequest_database["sidequests"][questgiver_id][quest_id]

        bot.edit_message_text(chat_id=chat_id,
                              message_id=query.message.message_id,
                              text="<b>Sidequests for %s:</b>\n\n" % get_name_from_database(questgiver_id),
                              reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(questgiver_id, questgiver_id)),
                              parse_mode="HTML")
    elif split_data[0] == "ARCHIVE":
        questgiver_id = int(split_data[1])
        quest_id = int(split_data[2])

        if user_id != questgiver_id:
            send_message(chat_id, "That's not your sidequest list!")
            return

        title, description, reward, accepters = sidequest_database["sidequests"][questgiver_id][quest_id]

        for accepter in accepters:
            send_message(accepter, "The sidequest, %s by %s, you were on was just archived!" % (title, get_name_from_database(questgiver_id)))

        sidequest_database["archives"][questgiver_id] = sidequest_database["sidequests"][questgiver_id][quest_id][:]
        del sidequest_database["sidequests"][questgiver_id][quest_id]

        bot.edit_message_text(chat_id=chat_id,
                              message_id=query.message.message_id,
                              text="<b>Sidequests for %s:</b>\n\n" % get_name_from_database(questgiver_id),
                              reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(questgiver_id, questgiver_id)),
                              parse_mode="HTML")
    elif split_data[0] == "EDIT":
        questgiver_id = int(split_data[1])
        quest_id = int(split_data[2])

        if user_id != questgiver_id:
            send_message(chat_id, "That's not your sidequest list!")
            return

        context.user_data["current_quest"] = quest_id
        send_message(chat_id, "Let's begin editing that sidequest! "
                              "First, send me a title, use /skiptitle, or use /removetitle. "
                              "You can cancel at any time using /cancel.")

        return TITLE
    elif split_data[0] == "DISPLAY":
        to_display_id = int(split_data[1])

        bot.send_message(chat_id=chat_id,
                         text="<b>Sidequests for %s:</b>\n\n" % get_name_from_database(to_display_id),
                         reply_markup=telegram.InlineKeyboardMarkup(
                             make_display_buttons(to_display_id, user_id)),
                         parse_mode=telegram.ParseMode.HTML)
    elif split_data[0] == "SHOW":
        questgiver_id = int(split_data[1])
        quest_id = int(split_data[2])

        title, description, reward, accepters = sidequest_database["sidequests"][questgiver_id][quest_id]

        send_message(chat_id, "<b>Title:</b> %s" % title + "\n\n<b>Description:</b> %s" % description + "\n\n<b>Reward:</b> %s" % reward)
    elif split_data[0] == "SHOWALL":
        for id, name in sidequest_database["users"]:
            if id != user_id and len(sidequest_database["sidequests"][id]) > 0:
                bot.send_message(chat_id=chat_id,
                                 text="<b>Sidequests for %s:</b>\n\n" % name,
                                 reply_markup=telegram.InlineKeyboardMarkup(make_display_buttons(id, user_id)),
                                 parse_mode=telegram.ParseMode.HTML)
    elif split_data[0] == "LIST":
        questgiver_id = int(split_data[1])
        quest_id = int(split_data[2])

        title, description, reward, accepters = sidequest_database["sidequests"][questgiver_id][quest_id]

        text = "The following people have accepted this sidequest:\n\n"
        for id in accepters:
            text += get_name_from_database(id) + "\n"
        send_message(chat_id, text)

    return ConversationHandler.END


def sidequest_handler(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    # Add a new empty sidequest.
    sidequest_database["sidequests"][update.message.from_user.id].append(["","","",[]])
    context.user_data["current_quest"] = len(sidequest_database["sidequests"][update.message.from_user.id]) - 1

    send_message(chat_id, "Let's begin adding a new sidequest! "
                          "First, send me a title, use /skiptitle, or use /removetitle. "
                          "You can cancel at any time using /cancel.")

    return TITLE


def add_title_handler(update, context):
    user = update.message.from_user
    title = update.message.text
    quest_id = context.user_data["current_quest"]
    chat_id = update.message.chat_id

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    sidequest_database["sidequests"][user.id][quest_id][0] = title

    update.message.reply_text("Now send me some text for the description, use /skipdesc, or use /removedesc.")

    return DESCRIPTION


def add_description_handler(update, context):
    user = update.message.from_user
    description = update.message.text
    quest_id = context.user_data["current_quest"]
    chat_id = update.message.chat_id

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    sidequest_database["sidequests"][user.id][quest_id][1] = description

    update.message.reply_text("Thanks! Lastly, you need to send some text for the reward, use /skipreward, or use /removereward.")

    return REWARD


def skip_title_handler(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    update.message.reply_text("No title added. Now send me some text for the description, use /skipdesc, or use /removedesc.")

    return DESCRIPTION


def skip_description_handler(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    update.message.reply_text("No description added. Lastly, you need to send some text for the reward, use /skipreward, or use /removereward.")

    return REWARD


def remove_title_handler(update, context):
    user = update.message.from_user
    quest_id = context.user_data["current_quest"]
    chat_id = update.message.chat_id

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    sidequest_database["sidequests"][user.id][quest_id][0] = ""

    update.message.reply_text("Alright, the title has been removed! Now send me some text for the description, use /skipdesc, or use /removedesc.")

    return DESCRIPTION


def remove_description_handler(update, context):
    user = update.message.from_user
    quest_id = context.user_data["current_quest"]
    chat_id = update.message.chat_id

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    sidequest_database["sidequests"][user.id][quest_id][1] = ""

    update.message.reply_text("That description has been removed! Lastly, you need to send some text for the reward, use /skipreward, or use /removereward.")

    return REWARD


def add_reward_handler(update, context):
    user = update.message.from_user
    reward = update.message.text
    quest_id = context.user_data["current_quest"]
    chat_id = update.message.chat_id

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    sidequest_database["sidequests"][user.id][quest_id][2] = reward

    update.message.reply_text("Thanks! You're all done!")

    text = "%s has added a new sidequest:" % get_name_from_database(user.id)
    buttons = [[telegram.InlineKeyboardButton(text="%s" % sidequest_database["sidequests"][user.id][quest_id][0], callback_data="SHOW,%s,%s" % (user.id, quest_id))]]

    for id, name in sidequest_database["users"]:
        if id != user.id:
            bot.send_message(chat_id=id,
                             text=text,
                             reply_markup=telegram.InlineKeyboardMarkup(buttons),
                             parse_mode=telegram.ParseMode.HTML)

    return ConversationHandler.END


def skip_reward_handler(update, context):
    chat_id = update.message.chat_id
    user = update.message.from_user
    quest_id = context.user_data["current_quest"]

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    update.message.reply_text("No reward added. You're all done!")

    text = "%s has added a new sidequest:" % get_name_from_database(user.id)
    buttons = [[telegram.InlineKeyboardButton(text="%s" % sidequest_database["sidequests"][user.id][quest_id][0], callback_data="SHOW,%s,%s" % (user.id, quest_id))]]

    for id, name in sidequest_database["users"]:
        if id != user.id:
            bot.send_message(chat_id=id,
                             text=text,
                             reply_markup=telegram.InlineKeyboardMarkup(buttons),
                             parse_mode=telegram.ParseMode.HTML)

    return ConversationHandler.END


def remove_reward_handler(update, context):
    user = update.message.from_user
    quest_id = context.user_data["current_quest"]
    chat_id = update.message.chat_id

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    sidequest_database["sidequests"][user.id][quest_id][2] = ""

    update.message.reply_text("The reward has been removed. You're all done!")

    text = "%s has added a new sidequest:" % get_name_from_database(user.id)
    buttons = [[telegram.InlineKeyboardButton(text="%s" % sidequest_database["sidequests"][user.id][quest_id][0], callback_data="SHOW,%s,%s" % (user.id, quest_id))]]

    for id, name in sidequest_database["users"]:
        if id != user.id:
            bot.send_message(chat_id=id,
                             text=text,
                             reply_markup=telegram.InlineKeyboardMarkup(buttons),
                             parse_mode=telegram.ParseMode.HTML)

    return ConversationHandler.END


def cancel_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return ConversationHandler.END

    send_message(chat_id, "Exited from sidequest creator!")

    return ConversationHandler.END


def archives_handler(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user

    if not check_profile_existence(user.id):
        send_message(chat_id, "You don't have a sidequest board yet! Make one using /am.")
        return

    send_message(chat_id, "<b>Your Archived Sidequests:</b>")
    for title, description, reward, accepters in sidequest_database["archives"][user.id]:
        send_message(chat_id, "<b>Title:</b> %s" % title + "\n\n<b>Description:</b> %s" % description + "\n\n<b>Reward:</b> %s" % reward + "\n\n<b>Accepters:</b> %s" % ",".join(accepters))


def feedback_handler(update, context):
    user = update.message.from_user

    username = ""
    for id, name in sidequest_database["users"]:
        if id == user.id:
            username = name
            break

    if context.args and len(context.args) > 0:
        feedback = open("feedback.txt", "a+")

        feedback.write(str(update.message.from_user.id) +
                       " (" + username + ") at " +
                       str(datetime.datetime.now()) + "\n")
        feedback.write(" ".join(context.args) + "\n\n")

        feedback.close()

        send_message(update.message.chat_id, text="Your response has been recorded!")
    else:
        send_message(update.message.chat_id, text="Error: You must input a non-empty string.")


def save_database(context):
    if os.path.exists("sidequestdatabase"):
        shutil.copy("sidequestdatabase", "sidequestdatabasebackup")
    pickle.dump(sidequest_database, open("sidequestdatabase", "wb"))


def handle_error(update, context):
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))
    ERROR_LOGGER.warning("Telegram Error! %s with context error %s caused by this update: %s", trace, context.error, update)


if __name__ == "__main__":
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Init setup

    if sidequest_database.get("sidequests") is None:
        sidequest_database["sidequests"] = defaultdict(list)

    if sidequest_database.get("users") is None:
        sidequest_database["users"] = []

    if sidequest_database.get("patches") is None:
        sidequest_database["patches"] = []

    if sidequest_database.get("archives") is None:
        sidequest_database["archives"] = defaultdict(list)

    # Static commands

    static_commands = ["start", "help"]
    for c in static_commands:
        dispatcher.add_handler(static_handler(c))

    # Main commands

    """
    
    Plan:
    
        -You can add a sidequest via a conversation (name, description, reward)
        -Anyone can see the list of users and find the sidequest list they want
        -Or they can use /display [name] or just /display for their own.
        -Looking at someone else's sidequest list presents the option to toggle accepting a quest, which notifies both people
        -Looking at your own gives you the option to delete a sidequest, archive it, or update it. There's also going to be a button for adding a new sidequest at the bottom.
    
    https://stackoverflow.com/questions/45558984/how-to-make-telegram-bot-dynamic-keyboardbutton-in-python-every-button-on-one-ro
    
    """

    sidequest_aliases = ["sidequest", "sq"]
    display_aliases = ["display", "view", "d"]
    users_aliases = ["users", "u"]
    add_me_aliases = ["addme", "setname", "am", "sn"]
    remove_me_aliases = ["removeme", "rm"]
    feedback_aliases = ["feedback", "report"]
    my_sidequests_aliases = ["mysidequests", "ms"]
    show_all_aliases = ["showall", "sa"]
    archives_aliases = ["archives"]
    #clear_aliases = ["clear"]

    commands = [("display", display_aliases),
                ("users", users_aliases),
                ("add_me", add_me_aliases),
                ("remove_me", remove_me_aliases),
                ("remove_me_confirmed", ["rmc"]),
                ("feedback", feedback_aliases),
                ("my_sidequests", my_sidequests_aliases),
                ("show_all", show_all_aliases),
                ("archives", archives_aliases)
                #("clear", clear_aliases)
                ]

    for base_name, aliases in commands:
        func = locals()[base_name + "_handler"]
        dispatcher.add_handler(CommandHandler(aliases, func))

    # Special conversation handler for creating/editing a sidequest.

    dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sidequest", sidequest_handler),
                      CallbackQueryHandler(button_handler)],

        states={
            TITLE: [MessageHandler(Filters.text & ~Filters.command, add_title_handler),
                    CommandHandler("skiptitle", skip_title_handler),
                    CommandHandler("removetitle", remove_title_handler)],

            DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, add_description_handler),
                  CommandHandler("skipdesc", skip_description_handler),
                  CommandHandler("removedesc", remove_description_handler)],

            REWARD: [MessageHandler(Filters.text & ~Filters.command, add_reward_handler),
                   CommandHandler("skipreward", skip_reward_handler),
                   CommandHandler("removereward", remove_reward_handler)]
        },

        fallbacks=[CommandHandler("cancel", cancel_handler)]
    ))

    # Button handler

    dispatcher.add_handler(CallbackQueryHandler(button_handler))

    # Set up job queue for repeating automatic tasks.

    jobs = updater.job_queue

    save_database_job = jobs.run_repeating(save_database, interval=3600, first=0)
    save_database_job.enabled = True

    # Error handler

    dispatcher.add_error_handler(handle_error)

    # Restart

    def stop_and_restart():
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def restart(update, context):
        save_database(context)
        update.message.reply_text('Bot is restarting...')
        Thread(target=stop_and_restart).start()

    dispatcher.add_handler(CommandHandler("restart",
                                          restart,
                                          filters=Filters.user(username='@thweaver')))

    # Ban

    dispatcher.add_handler(CommandHandler("ban", ban_handler, pass_args=True, filters=Filters.user(username='@thweaver')))

    # Run the bot

    send_patchnotes()

    updater.start_polling()
    updater.idle()
