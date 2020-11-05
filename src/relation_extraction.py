import argparse
import torch
import numpy as np
import random
from utils import TransformerLogger
from task import TaskRunner
from pathlib import Path
from data_processing.io_utils import save_text
import traceback


def set_seed(gargs):
    random.seed(gargs.seed)
    np.random.seed(gargs.seed)
    torch.manual_seed(gargs.seed)


def app(gargs):
    set_seed(gargs)

    # do_eval is used with do_train in most cases for 5-CV
    if gargs.do_eval and not gargs.do_train:
        raise RuntimeError("Evaluation mode (do_eval) is only available when do_train is used.\n"
                           "You may want to use do_predict instead.")

    # make it case in-sensitive
    gargs.model_type = gargs.model_type.lower()
    task_runner = TaskRunner(gargs)
    if gargs.do_train:
        if Path(gargs.new_model_dir).exists() and not gargs.overwrite_model_dir:
            raise RuntimeError("{} is exist and overwrite this dir is not permitted.".format(gargs.new_model_dir))

        # training
        try:
            task_runner.train()
        except:
            gargs.logger.error("Training error:\n{}".format(traceback.format_exc()))
            raise RuntimeError(traceback.format_exc())

        if gargs.do_eval:
            # eval on dev
            try:
                eval_res = task_runner.eval()
            except:
                gargs.logger.error("Evaluation error:\n{}".format(traceback.format_exc()))
                raise RuntimeError(traceback.format_exc())

            gargs.logger.info("eval performance:\n{}".format(eval_res))
            eval_output = ""
            for k, v in eval_res.items():
                eval_output += "{}:{}\n".format(k, v)
            save_text(eval_output, gargs.new_model_dir/"eval_result.txt")

    if gargs.do_predict:
        # run prediction
        try:
            preds = task_runner.predict()
        except:
            gargs.logger.error("Prediction error:\n{}".format(traceback.format_exc()))
            raise RuntimeError(traceback.format_exc())

        pred_res = "\n".join([str(pred) for pred in preds])

        # predict_output_file must be a file, we will create parent dir automatically
        Path(gargs.predict_output_file).parent.mkdir(parents=True, exist_ok=True)
        save_text(pred_res, gargs.predict_output_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # parse arguments
    parser.add_argument("--model_type", default='bert', type=str, required=True,
                        help="valid values: bert, roberta, albert or xlnet")
    parser.add_argument("--data_format_mode", default=0, type=int,
                        help="valid values: 0: sep mode - [CLS]S1[SEP]S2[SEP]; 1: uni mode - [CLS]S1S2[SEP]")
    parser.add_argument("--classification_scheme", default=0, type=int,
                        help="special tokens used for classification. "
                             "Valid values: 0: [CLS]; 1: [CLS], [S1], [S2]; 2: [CLS], [S1], [S2], [E1], [E2]")
    parser.add_argument("--pretrained_model", type=str,
                        help="The pretrained model file or directory for fine tuning.")
    parser.add_argument("--data_dir", type=str, required=True,
                        help="The input data directory. Should have at least a file named train.tsv")
    parser.add_argument("--new_model_dir", type=str, required=True,
                        help="directory for saving new model checkpoints (keep latest n only)")
    parser.add_argument("--predict_output_file", type=str, default=None,
                        help="predicted results output file.")
    parser.add_argument('--overwrite_model_dir', action='store_true',
                        help="Overwrite the content of the new model directory")
    parser.add_argument("--seed", default=3, type=int,
                        help='random seed')
    parser.add_argument("--max_seq_length", default=512, type=int,
                        help="maximum number of tokens allowed in each sentence")
    parser.add_argument("--cache_data", action='store_true',
                        help="Whether to cache the features after tokenization (save training initialization time)")
    parser.add_argument("--do_train", action='store_true',
                        help="Whether to run training.")
    parser.add_argument("--do_eval", action='store_true',
                        help="Whether to run evaluation on dev.")
    parser.add_argument("--do_predict", action='store_true',
                        help="Whether to run prediction on the test set.")
    parser.add_argument("--do_lower_case", action='store_true',
                        help="Set this flag if you are using an uncased model.")
    parser.add_argument("--train_batch_size", default=8, type=int,
                        help="The batch size for training.")
    parser.add_argument("--eval_batch_size", default=8, type=int,
                        help="The batch size for eval.")
    parser.add_argument("--learning_rate", default=1e-5, type=float,
                        help="The initial learning rate for Adam.")
    parser.add_argument("--num_train_epochs", default=10, type=int,
                        help="Total number of training epochs to perform.")
    parser.add_argument('--gradient_accumulation_steps', type=int, default=1,
                        help="Number of updates steps to accumulate before performing a backward/update pass.")
    parser.add_argument("--do_warmup", action='store_true',
                        help='Whether to apply warmup strategy in optimizer.')
    parser.add_argument("--warmup_ratio", default=0.1, type=float,
                        help="Linear warmup over warmup_ratio.")
    parser.add_argument("--weight_decay", default=0.0, type=float,
                        help="Weight deay if we apply some.")
    parser.add_argument("--adam_epsilon", default=1e-8, type=float,
                        help="Epsilon for Adam optimizer.")
    parser.add_argument("--max_grad_norm", default=1.0, type=float,
                        help="Max gradient norm.")
    parser.add_argument("--max_num_checkpoints", default=3, type=int,
                        help="max number of checkpoints saved during training, old checkpoints will be removed.")
    parser.add_argument("--log_file", default=None,
                        help="where to save the log information")
    parser.add_argument("--log_lvl", default="i", type=str,
                        help="d=DEBUG; i=INFO; w=WARNING; e=ERROR")
    parser.add_argument("--log_step", default=1000, type=int,
                        help="logging after how many steps of training. If < 0, no log during training")
    parser.add_argument("--progress_bar", action='store_true',
                        help="show progress during the training in tqdm")
    parser.add_argument('--fp16', action='store_true',
                        help="Whether to use 16-bit float precision instead of 32-bit")
    parser.add_argument("--fp16_opt_level", type=str, default="O1",
                        help="For fp16: Apex AMP optimization level selected in ['O0', 'O1', 'O2', and 'O3']."
                             "See details at https://nvidia.github.io/apex/amp.html")

    args = parser.parse_args()

    # other setup
    args.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.logger = TransformerLogger(logger_file=args.log_file, logger_level='i').get_logger()
    app(args)
